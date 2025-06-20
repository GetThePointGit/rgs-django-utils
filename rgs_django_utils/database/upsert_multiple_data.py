import collections
import logging
import typing
from typing import Type

from django.db import connection
from django.db.models import Model
from psycopg import sql

from rgs_django_utils.database.db_types import ImportMethod

# todo: needed in psycopg3?
# from psycopg2.extensions import register_adapter
# from psycopg2.extras import Json
# register_adapter(dict, Json)

log = logging.getLogger(__name__)


def _get_data_row(data, cols):
    out = []
    for col in cols:
        out.append(data.get(col.get("name")))
    return out


def _get_mogrify_template(cols, model: Type[Model]):
    out = []
    for col in cols:
        dtype = _get_postgres_field_type(col, model)
        if dtype.startswith("geometry"):
            if "4326" in dtype:
                out.append("ST_TRANSFORM(ST_GeomFromText(%s), 4326)")
            else:
                out.append("ST_GeomFromText(%s)")
        elif dtype.lower().startswith("json"):
            out.append("%s")
        else:
            out.append("%s")

    return "(" + ",".join(out) + ")"


class NotAvailable:
    pass


def _get_postgres_field_type(field_name, model: Type[Model]):
    field = model._meta.get_field(field_name)
    db_type = field.cast_db_type(connection)

    db_type = db_type.replace("(%(max_length)s)", "")

    if db_type.lower() == "bigserial":
        db_type = "bigint"
    elif db_type.lower() == "serial":
        db_type = "int"

    return db_type


def upsert_from_existing_data(
    model: Type[Model],
    source_table_name: str,
    cols: typing.List[typing.Dict[str, typing.Any]],
    update_field_names: typing.List[str],
    identification_field_names: typing.List[str] = None,
    method: str = ImportMethod.OVERWRITE,
    source_schema: str = "public",
):
    cols_dict = collections.OrderedDict((col.get("target"), col) for col in cols)

    pk_field = model._meta.pk.name
    if identification_field_names is None:
        identification_field_names = [pk_field]

    # remove identification_field_names from update_field_names
    update_field_names = [field for field in update_field_names if field not in identification_field_names]

    combined_field_names = identification_field_names + update_field_names

    with connection.cursor() as cursor:
        target_table = sql.Identifier(model._meta.db_table)
        source_table = sql.SQL("{source_schema}.{source_table_name}").format(
            source_schema=sql.Identifier(source_schema),
            source_table_name=sql.Identifier(source_table_name),
        )

        index_cols_source_table = []

        for id_col in identification_field_names:
            col = cols_dict.get(id_col)
            if col is None:
                raise ValueError(f"field {id_col} not found in cols")
            if col.get("value", NotAvailable) != NotAvailable:
                # value provided, no need to index
                continue

            source_col = col.get("source", col.get("target", id_col))

            index_cols_source_table.append(
                sql.SQL("""
                    CREATE INDEX IF NOT EXISTS {index_name}
                    ON {source_table} USING btree
                    ({source_col} ASC NULLS LAST);
                """).format(
                    index_name=sql.Identifier(f"{source_table_name}_id_{source_col}"),
                    source_table=source_table,
                    source_col=sql.Identifier(source_col),
                )
            )
        index_cols_source_table = sql.SQL("\n").join(index_cols_source_table)

        # for update part, the set columns and values are determined
        set_cols = []
        set_values = {}
        for field_name in update_field_names:
            col = cols_dict.get(field_name)
            if col is None:
                raise ValueError(f"field {field_name} not found in cols")

            if col.get("value", NotAvailable) != NotAvailable:
                set_cols.append(
                    sql.SQL("{target_col}={target_col_value}").format(
                        target_col=sql.Identifier(col.get("target")),
                        target_col_value=sql.Literal(col.get("value")),
                    )
                )
                set_values[col.get("target")] = col.get("value")
            else:
                set_cols.append(
                    sql.SQL("{target_col}={source_table}.{source_col}").format(
                        source_table=source_table,
                        target_col=sql.Identifier(col.get("target")),
                        source_col=sql.Identifier(col.get("source", col.get("target"))),
                    )
                )
        set_cols = sql.SQL(",").join(set_cols)

        insert_target_cols = []
        insert_source_cols = []
        insert_values = {}
        for col in cols:
            if col is None:
                raise ValueError(f"field {field_name} not found in cols")

            insert_target_cols.append(sql.Identifier(col.get("target")))
            if col.get("value", NotAvailable) != NotAvailable:
                insert_source_cols.append(
                    sql.SQL("{target_col_value}").format(
                        target_col_value=sql.Literal(col.get("value")),
                    )
                )
                insert_values[col.get("target")] = col.get("value")
            else:
                insert_source_cols.append(
                    sql.SQL("{source_table}.{source_col}").format(
                        source_table=source_table,
                        source_col=sql.Identifier(col.get("source", col.get("target"))),
                    )
                )
        insert_target_cols = sql.SQL(",").join(insert_target_cols)
        insert_source_cols = sql.SQL(",").join(insert_source_cols)

        where_cols = []
        where_values = {}
        for field_name in identification_field_names:
            col = cols_dict.get(field_name)
            if col is None:
                raise ValueError(f"field {field_name} not found in cols")

            if col.get("value", NotAvailable) != NotAvailable:
                where_cols.append(
                    sql.SQL("target_table.{target_col}={target_col_value}").format(
                        # target_table=target_table,
                        target_col=sql.Identifier(col.get("target")),
                        target_col_value=sql.Literal(col.get("value")),
                    )
                )
                where_values[col.get("target")] = col.get("value")
            else:
                where_cols.append(
                    sql.SQL("target_table.{target_col}={source_table}.{source_col}").format(
                        # target_table=target_table,
                        target_col=sql.Identifier(col.get("target")),
                        source_table=source_table,
                        source_col=sql.Identifier(col.get("source", col.get("target"))),
                    )
                )
        where_cols = sql.SQL(" AND ").join(where_cols)

        if method == ImportMethod.ONLY_NEW or not len(update_field_names):
            update_part = None
        else:
            update_part = sql.SQL("""
                WITH upd as (UPDATE {target_table} target_table
                SET {set_cols}
                FROM {source_table}
                WHERE {where_cols} 
                RETURNING *)
                SELECT count(*) as updated FROM upd;
            """).format(
                target_table=target_table,
                set_cols=set_cols,
                source_table=source_table,
                where_cols=where_cols,
            )

        if method == ImportMethod.ONLY_UPDATE:
            insert_part = None
        else:
            insert_part = sql.SQL("""
                WITH ins as (INSERT INTO {target_table} ({insert_target_cols})
                SELECT {insert_source_cols}
                FROM {source_table}
                LEFT OUTER JOIN {target_table} target_table ON ({where_cols})
                WHERE target_table.{pk_field_target_table} IS NULL 
                RETURNING *)
                SELECT count(*) as inserted FROM ins;
            """).format(
                target_table=target_table,
                insert_target_cols=insert_target_cols,
                insert_source_cols=insert_source_cols,
                source_table=source_table,
                where_cols=where_cols,
                pk_field_target_table=sql.Identifier(pk_field),
            )

        if method == ImportMethod.REPLACE:
            log.warning("REPLACE method is not implemented yet")

        updated = 0
        inserted = 0

        cursor.execute("BEGIN;")
        # --SET LOCAL tapp.skip_recalc_flagging = true;
        cursor.execute(index_cols_source_table)
        # table will be unlocked after commit
        cursor.execute(
            sql.SQL("LOCK TABLE {target_table} IN EXCLUSIVE MODE;").format(
                target_table=target_table,
            )
        )

        if update_part:
            # print(update_part.as_string(cursor.connection))
            values = {**set_values, **where_values}
            # print(values)
            # print(update_part.as_string(cursor.connection))
            cursor.execute(update_part, values)
            updated = cursor.fetchone()[0]
        if insert_part:
            # print(insert_part.as_string(cursor.connection))
            cursor.execute(insert_part, {**insert_values, **where_values})
            inserted = cursor.fetchone()[0]
        # --SET LOCAL tapp.skip_recalc_flagging = false;
        cursor.execute("COMMIT;")

    return updated, inserted


def upsert_multiple_data(
    model: Type[Model],
    data: typing.List[typing.Tuple | typing.List | typing.Dict],
    data_fields: typing.List[str],
    update_field_names: typing.List[str],
    identification_field_names: typing.List[str] = None,
    method: str = ImportMethod.OVERWRITE,
    page_size: int = 1000,
):
    # todo: return counts over inserts, updates and skipped
    # todo: Add support for ImportMethod.REPLACE, optionally with set field to false or true
    # todo: add tests for this function

    if not len(data):
        log.info("upsert_multiple_data has no records for table %s", model._meta.db_table)

    pk_field = model._meta.pk.name
    if identification_field_names is None:
        identification_field_names = [pk_field]

    # remove identification_field_names from update_field_names
    update_field_names = [field for field in update_field_names if field not in identification_field_names]

    combined_field_names = identification_field_names + update_field_names

    # make table (list of list) for the data with correctly ordered columns
    total_data = []
    if isinstance(data[0], dict):
        for item in data:
            total_data.append([item.get(col) for col in combined_field_names])
    elif isinstance(data[0], (tuple, list)):
        # map data order from data_fields to combined_field_names
        data_field_map = {field: combined_field_names.index(field) for field in data_fields}

        for field in identification_field_names:
            if field not in data_fields:
                raise ValueError(f"id field {field} is required in data_fields for model {model.__name__}")

        for item in data:
            total_data.append([item[data_field_map.get(col)] for col in combined_field_names])
    # is this required?: with connection.cursor().connection.cursor() as cursor:

    with connection.cursor() as cursor:
        template = _get_mogrify_template(combined_field_names, model)

        table = sql.Identifier(model._meta.db_table)
        cols_with_definition = sql.Composed(
            [
                sql.SQL("{col} {ftype}").format(
                    col=sql.Identifier(col), ftype=sql.SQL(_get_postgres_field_type(col, model))
                )
                for col in combined_field_names
            ]
        ).join(", ")
        cols = sql.SQL(",").join(map(lambda col: sql.Identifier(col), combined_field_names))
        index_cols = sql.SQL("\n").join(
            map(
                lambda col: sql.SQL("""
                    CREATE INDEX {index_name}
                    ON newvals USING btree
                    ({col} ASC NULLS LAST);
                """).format(col=sql.Identifier(col), index_name=sql.Identifier(f"newvals_id_{col}")),
                identification_field_names,
            )
        )
        # todo: combined columns?!?
        set_cols = sql.SQL(",").join(
            map(lambda col: sql.SQL("{col}=newvals.{col}").format(col=sql.Identifier(col)), update_field_names)
        )
        insert_cols = sql.SQL(",").join(map(lambda col: sql.Identifier(col), combined_field_names))
        where_cols = sql.SQL(" AND ").join(
            map(
                lambda col: sql.SQL("target_table.{col}=newvals.{col}").format(col=sql.Identifier(col)),
                identification_field_names,
            )
        )

        if method == ImportMethod.ONLY_NEW or not len(update_field_names):
            update_part = sql.SQL("")
        else:
            update_part = sql.SQL("""
                UPDATE {table} target_table
                SET {set_cols}
                FROM newvals
                WHERE {where_cols};
            """).format(
                table=table,
                set_cols=set_cols,
                where_cols=where_cols,
            )
        if method == ImportMethod.ONLY_UPDATE:
            insert_part = sql.SQL("")
        else:
            insert_part = sql.SQL("""
                INSERT INTO {table} ({insert_cols})
                SELECT {newvals_cols}
                FROM newvals
                LEFT OUTER JOIN {table} target_table ON ({where_cols})
                WHERE target_table.{pk_field_target_table} IS NULL;
            """).format(
                table=table,
                insert_cols=insert_cols,
                where_cols=where_cols,
                pk_field_target_table=sql.Identifier(pk_field),
                newvals_cols=sql.SQL(",").join(
                    map(
                        lambda col: sql.SQL("{}.{}").format(sql.Identifier("newvals"), sql.Identifier(col)),
                        combined_field_names,
                    )
                ),
            )

        if method == ImportMethod.REPLACE:
            log.warning("REPLACE method is not implemented yet")

        page = 0

        while True:
            data = ",".join(
                [cursor.mogrify(template, item) for item in total_data[page * page_size : (page + 1) * page_size]]
            )

            page += 1
            if not data:
                break

            sql_data = sql.SQL(data)

            sql_query = sql.SQL("""
                BEGIN;
                --SET LOCAL tapp.skip_recalc_flagging = true;

                CREATE TEMPORARY TABLE newvals({cols_with_definition});

                INSERT INTO newvals({cols}) VALUES {sql_data};      
                {index_cols};

                -- table will be unlocked after commit
                LOCK TABLE {table} IN EXCLUSIVE MODE;
                {update_part}
                {insert_part}

                DROP TABLE newvals;
                --SET LOCAL tapp.skip_recalc_flagging = false;
                COMMIT;
            """).format(
                table=table,
                cols_with_definition=cols_with_definition,
                cols=cols,
                sql_data=sql_data,
                index_cols=index_cols,
                update_part=update_part,
                insert_part=insert_part,
            )

            log.debug(sql_query.as_string(cursor.connection))
            cursor.execute(sql_query)
