import logging
import time
from typing import List

import django
import django.apps
from django.db import connection, models, transaction

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django()


from rgs_django_utils.database.base_models.enums import BaseEnum, BaseEnumExtended
from rgs_django_utils.database.db_types import ImportMethod
from rgs_django_utils.database.upsert_multiple_data import upsert_multiple_data

log = logging.getLogger(__name__)


def reset_autofield_sequence(model):
    """Reset the Postgres sequence behind a model's ``AutoField`` primary key.

    After bulk-inserting rows with explicit ids (common in fixtures/seed
    data), the auto-generated sequence still points at 1. Any subsequent
    ``INSERT`` without an explicit id then collides with existing rows.
    This helper fast-forwards the sequence to ``MAX(pk)`` so new inserts
    resume correctly.

    Parameters
    ----------
    model : type[django.db.models.Model]
        Model whose primary-key sequence is reset. Silently returns when
        the pk is not an ``AutoField``/``BigAutoField``.
    """
    pk_field = model._meta.pk
    if pk_field is None or not isinstance(pk_field, (models.AutoField, models.BigAutoField)):
        return

    table = model._meta.db_table
    column = pk_field.column
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT setval(pg_get_serial_sequence(%s, %s), GREATEST(COALESCE(MAX("{column}"), 1), 1)) FROM "{table}"',
            [table, column],
        )
    log.info("Reset sequence for %s.%s", table, column)


def get_value_helper(value):
    """Format *value* as a SQL literal (``'s'``-quoted string or bare number)."""
    if value is None:
        return "null"
    if isinstance(value, str):
        return "'{}'".format(value.replace("'", ""))
    return str(value)


def get_install_order_from_model(model, default_order=10):
    """Return the install order for *model* — enum tables sort first (``0``).

    Non-enum models honour ``model.TableDescription.db_install_order`` when
    present, otherwise fall back to *default_order*.

    Parameters
    ----------
    model : type[django.db.models.Model]
        Model whose install order is being resolved.
    default_order : int, optional
        Fallback when nothing more specific is configured. Default is
        ``10``.
    """
    if issubclass(model, BaseEnum) or issubclass(model, BaseEnumExtended):
        return 0

    if hasattr(model, "TableDescription"):
        return getattr(model.TableDescription, "db_install_order", default_order)

    return default_order


def add_default_records(model_selection: List[str] = None, *args, **kwargs):
    """Populate the database with every model's seed / default records.

    Iterates over all installed Django models and for each one that exposes
    either ``default_records()`` (data-driven) or ``custom_default_records()``
    (imperative) it upserts the rows. Models are processed in the order
    returned by :func:`get_install_order_from_model`, wrapped in a single
    transaction and followed by :func:`reset_autofield_sequence` to keep
    auto sequences consistent.

    Parameters
    ----------
    model_selection : list of str, optional
        If supplied, only models whose ``db_table`` is in the list are
        processed. ``None`` (the default) processes every model.

    Notes
    -----
    * Only models in the ``public`` schema are touched.
    * Two model contracts are recognised:

      ``default_records`` — classmethod returning a dict with
      ``fields`` / ``data`` (list of tuples or dicts) and optionally
      ``id_fields`` and ``method``. The rows are upserted via
      :func:`~rgs_django_utils.database.upsert_multiple_data.upsert_multiple_data`.

      ``custom_default_records`` — imperative classmethod that creates or
      updates records itself, typically via ``get_or_create``.

    Examples
    --------
    Declarative form — a simple enum table seeded from a tuple list::

        class Severity(models.Model):
            id = TextStringField(primary_key=True)
            name = TextStringField()

            class Meta:
                db_table = "enum_severity"

            @classmethod
            def default_records(cls):
                return {
                    "fields": ["id", "name"],
                    "data": [("low", "Low"), ("high", "High")],
                }

    Imperative form — when the seed logic is not a pure upsert::

        class Measurement(models.Model):
            level = models.IntegerField()
            label = TextStringField()

            @classmethod
            def custom_default_records(cls):
                for lvl, lbl in [(1, "Niveau 1"), (5, "Niveau 2")]:
                    cls.objects.update_or_create(level=lvl, defaults={"label": lbl})
    """
    log.info("add default records to database")
    start_time = time.time()
    start_process_time = time.process_time()

    transaction.set_autocommit(False)

    list_of_models_to_process = []

    for model in django.apps.apps.get_models():
        if model._meta.abstract:
            continue

        if model_selection is not None and model._meta.db_table not in model_selection:
            continue

        if hasattr(model, "default_records") or hasattr(model, "custom_default_records"):
            list_of_models_to_process.append({"order": get_install_order_from_model(model), "model": model})

    list_of_models_to_process.sort(key=lambda m: m.get("order"))

    for modelset in list_of_models_to_process:
        model = modelset.get("model")
        print(f"Processing model {model}")

        if hasattr(model, "default_records"):
            log.info("add default records for %s.", str(model))

            default_records = model.default_records()

            fields = default_records.get("fields", [])
            data = default_records.get("data", [])
            id_fields = default_records.get("id_fields")

            if len(data) > 0:
                # make sure the fields are lists, not dicts
                if isinstance(data[0], dict):
                    data = [[r.get(f) for f in fields] for r in data]

                # if enum model, only keep id and name fields
                if issubclass(model, BaseEnum) and not (
                    issubclass(model, BaseEnumExtended) and getattr(model, "is_extended", False)
                ):
                    index_id = fields.index("id")
                    index_name = fields.index("name")

                    fields = ["id", "name"]
                    data = [(r[index_id], r[index_name]) for r in data]

                upsert_multiple_data(
                    model=model,
                    data=data,
                    data_fields=fields,
                    update_field_names=fields,
                    identification_field_names=id_fields,
                    method=default_records.get("method", ImportMethod.OVERWRITE),
                    # records worden default aangevuld om ongewenste mutaties te voorkomen. Todo: more advanced?
                )

        if hasattr(model, "custom_default_records"):
            log.info("add custom records for %s.", str(model))
            model.custom_default_records()

        reset_autofield_sequence(model)

    transaction.commit()
    transaction.set_autocommit(True)
    log.info(
        "finished adding default records to database in %.2f seconds (%.2f)",
        time.time() - start_time,
        time.process_time() - start_process_time,
    )


if __name__ == "__main__":
    add_default_records()
