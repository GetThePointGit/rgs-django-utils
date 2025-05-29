import logging

import django.apps
from django.db import connection, transaction
from django.db import models as dj_models
from django.db.models.fields import NOT_PROVIDED
from psycopg import sql

log = logging.getLogger(__name__)


if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django()


def install_db_defaults_and_relation_cascading(*args, **kwargs):
    """add default values defined in django and cascading to the database
    (so defaults and delete cascading are also available for Hasura).

    restrictions:
    - only static values (functions must be manually added as postgres trigger function)
    - default for uuid is always a random uuid7
    - no defaults for datetime fields (must be manually set with a trigger function)
    - only for schema public
    - only CASCADE, SET_NULL and SET_DEFAULT supported

    """
    log.info("install field default values to database (for Hasura)")

    models = django.apps.apps.get_models()

    count = 0
    with connection.cursor() as cursor:
        cursor.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
        for model in models:
            if model._meta.abstract:
                continue
            for field in model._meta.fields:
                # try to map defaults and django defaults to python functions
                db_table = model._meta.db_table
                column = field.column

                if hasattr(field, "r_config") and getattr(field.r_config, "default_function", None):
                    cursor.execute(
                        sql.SQL("""
                        ALTER TABLE ONLY {db_table} ALTER COLUMN {column} 
                        SET DEFAULT {function};
                    """).format(
                            db_table=sql.Identifier(db_table),
                            column=sql.Identifier(column),
                            function=sql.SQL(field.r_config.default_function),
                        )
                    )
                    count += 1
                elif hasattr(field, "auto_now_add") and field.auto_now_add:
                    cursor.execute(
                        sql.SQL("""
                        ALTER TABLE ONLY {db_table} ALTER COLUMN {column} 
                        SET DEFAULT NOW();
                    """).format(db_table=sql.Identifier(db_table), column=sql.Identifier(column))
                    )
                    count += 1
                elif hasattr(field, "auto_now") and field.auto_now:
                    cursor.execute(
                        sql.SQL("""
                            ALTER TABLE ONLY {db_table} ALTER COLUMN {column} 
                            SET DEFAULT NOW();
                        """).format(db_table=sql.Identifier(db_table), column=sql.Identifier(column))
                    )

                    log.info(
                        "!! default for {}.{} must be set with update trigger to NOW()".format(
                            model._meta.db_table, field.column
                        )
                    )
                elif (field.default != NOT_PROVIDED) and (field.default is not None):
                    if field.default == list:
                        cursor.execute(
                            sql.SQL("""
                            ALTER TABLE ONLY {db_table} ALTER COLUMN {column} 
                            SET DEFAULT array[]::integer[];
                        """).format(db_table=sql.Identifier(db_table), column=sql.Identifier(column))
                        )
                        count += 1
                    elif callable(field.default):
                        log.info(
                            f"!! default for {db_table}.{column} with "
                            f"function '{str(field.default)}' must be set with creation trigger."
                        )
                    else:
                        value = field.default
                        cursor.execute(
                            sql.SQL("""
                            ALTER TABLE ONLY {db_table} ALTER COLUMN {column} 
                            SET DEFAULT %(value)s;
                            """).format(db_table=sql.Identifier(db_table), column=sql.Identifier(column)),
                            {"value": value},
                        )
                        count += 1

                if field.is_relation:
                    if field.many_to_one or field.one_to_one:
                        action = "NO ACTION"
                        if field.remote_field.on_delete == dj_models.CASCADE:
                            action = "CASCADE"
                        elif field.remote_field.on_delete == dj_models.SET_NULL:
                            action = "SET NULL"
                        elif field.remote_field.on_delete == dj_models.SET_DEFAULT:
                            action = "SET DEFAULT"
                        else:
                            continue

                        cursor.execute(
                            """
                            SELECT c.confrelid::regclass::text AS referenced_table
                              ,string_agg(f.attname, ', ') AS referenced_columns
                              ,c.conname AS fk_name
                              ,pg_get_constraintdef(c.oid) AS fk_definition
                            FROM pg_attribute  a 
                            JOIN pg_constraint c ON (c.conrelid, c.conkey[1]) = (a.attrelid, a.attnum)
                            JOIN pg_attribute  f ON f.attrelid = c.confrelid
                                              AND f.attnum = ANY (confkey)
                            WHERE c.contype  = 'f'
                            AND a.attrelid = %(table)s::regclass
                            AND a.attname  = %(column)s 
                            GROUP  BY c.confrelid, c.conname, c.oid;
                        """,
                            {"table": f"public.{db_table}", "column": field.column},
                        )
                        constraint = cursor.fetchone()

                        if constraint is None:
                            log.warning("constraint for %s.%s not found.", db_table, column)
                            continue

                        transaction.set_autocommit(False)

                        query = sql.SQL("ALTER TABLE {db_table} DROP CONSTRAINT {constraint};").format(
                            db_table=sql.Identifier(db_table), constraint=sql.Identifier(constraint[2])
                        )
                        log.debug("query: %s", query.as_string(cursor.connection))
                        cursor.execute(query)

                        query = sql.SQL("""
                            ALTER TABLE {db_table} ADD CONSTRAINT {constraint} FOREIGN KEY ({column}) 
                            REFERENCES {ref_table} ({ref_column}) 
                            MATCH SIMPLE ON DELETE {action} DEFERRABLE INITIALLY IMMEDIATE;
                        """).format(
                            db_table=sql.Identifier(db_table),
                            column=sql.Identifier(column),
                            constraint=sql.Identifier(constraint[2]),
                            ref_table=sql.Identifier(field.related_model()._meta.db_table),
                            ref_column=sql.Identifier(field.remote_field.get_related_field().column),
                            action=sql.SQL(action),
                        )
                        log.debug("query: %s", query.as_string(cursor.connection))
                        cursor.execute(query)
                        connection.commit()
                        transaction.set_autocommit(True)

        log.info("add defaults for %i fields", count)


if __name__ == "__main__":
    install_db_defaults_and_relation_cascading()
