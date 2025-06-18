import logging
import time
from typing import List

import django
import django.apps
from django.db import transaction

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django()


from rgs_django_utils.database.base_models.enums import BaseEnum, BaseEnumExtended
from rgs_django_utils.database.db_types import ImportMethod
from rgs_django_utils.database.upsert_multiple_data import upsert_multiple_data

log = logging.getLogger(__name__)


def get_value_helper(value):
    if value is None:
        return "null"
    if type(value) == str:
        return "'{}'".format(value.replace("'", ""))
    return str(value)


def get_install_order_from_model(model, default_order=10):
    if issubclass(model, BaseEnum) or issubclass(model, BaseEnumExtended):
        return 0

    if hasattr(model, "TableDescription"):
        return getattr(model.TableDescription, "db_install_order", default_order)

    return default_order


def add_default_records(model_selection: List[str] = None, *args, **kwargs):
    """Add or update default values defined in django to the database.

    :param model_selection: list of model names to process

    Create the basic set of options for (enum) tables.
    To options are available:
    - default_records: based on a list of tuples with data. The id field is used as id field.
    - custom_default_records: custom function is called and this function must add or update records.

    Could be used after creation or updating of the database (see also management command).
    Will be applied to models which has the function 'get_default_choices' or 'get_default_choices_with_description'
    Specify attribute 'database_install_order' on a model to control order of models processed (default value = 0 for
    'get_default_choices' or 'get_default_choices_with_description' and 1 for 'install_default_records')

    # option 1
    class SomethingWithDefaultRecords(models.Model):
        # example of model with get_default_choices

        OPTION_ONE = 'one'
        OPTION_TWO = 'two'

        id = TextStringField(primary_key=True, blank=True, serialize=True)
        name = TextStringField(blank=True, editable=False)
        order = models.IntegerField(blank=True, editable=False)

        class Meta:
            db_table = "enum_something"

        class TableDescription:
            database_install_order = 2

        @classmethod
        def default_records(cls):
            return dict(
                fields=['id', 'name', 'order'],
                data=[
                (cls.OPTION_ONE, 'one is this', 1),
                (cls.OPTION_TWO, 'two is this', 2),
                ]
            )

    # options 2
    class SomethingWithCustomDefaultRecords(models.Model):
        # example of model with install_default_records

        a = models.IntegerField()
        b = TextStringField()

        class Meta:
            db_table = "something_with_default_records"

        class TableDescription:
            database_install_order = 3

        @classmethod
        def custom_default_records(cls):
            data = (
                (1, 'Niveau 1'),
                (5, 'Niveau 2'),
            )

            for conf in data:
                wnm, new = cls.objects.get_or_create(
                    a=conf[0],
                    defaults={
                        'b': conf[1]
                    }
                )
                if not new:
                    wnm.b = conf[1]
                    wnm.save()

    restrictions:
    - models in schema public
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

    transaction.commit()
    transaction.set_autocommit(True)
    log.info(
        "finished adding default records to database in %.2f seconds (%.2f)",
        time.time() - start_time,
        time.process_time() - start_process_time,
    )


if __name__ == "__main__":
    add_default_records()
