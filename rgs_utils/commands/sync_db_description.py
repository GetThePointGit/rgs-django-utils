import logging
import typing

from django.apps import apps
from django.db import models as dj_models

log = logging.getLogger(__name__)

if __name__ == "__main__":
    from rgs_utils.setup_django import setup_django

    setup_django(log)

from core.models.enums.module import EnumModule
from rgs_utils.database.dj_extended_models import Config, TableSection, section_register
from rgs_utils.models import (
    DescriptionField,
    DescriptionFieldInputForCalc,
    DescriptionFieldSection,
    DescriptionTable,
    DescriptionTableSection,
)

_available_modules = [
    EnumModule.DATA,
    EnumModule.MJP,
    EnumModule.VOORBEREIDING,
    EnumModule.METINGEN,
    EnumModule.UITVOERING,
]
_all_modules_str = "".join(_available_modules)


def get_modules_string(modules: str | typing.Iterable[typing.AnyStr | "EnumModule"]) -> str:
    """Get the modules from the EnumModule class.

    :param modules: The modules to get.
    :return: The modules.
    """

    if modules == "*":
        return _all_modules_str
    if isinstance(modules, str):
        if modules not in _all_modules_str:
            raise ValueError(f"Module {modules} not found")
        return "".join([m if m == modules else "." for m in _available_modules])
    if not all(module in _available_modules for module in modules):
        raise ValueError(f"Module {modules} not found")
    return "".join([m if m in modules else "." for m in _available_modules])


def sync_db_meta_tables():
    """Sync django extended model description to description tables.

    :return:
    """
    # first delete all tables. todo: find better way to remove unused stuff (so id's stay the same)
    DescriptionTable.objects.all().delete()
    DescriptionField.objects.all().delete()
    DescriptionTableSection.objects.all().delete()
    DescriptionFieldSection.objects.all().delete()
    DescriptionFieldInputForCalc.objects.all().delete()

    log.info("sync table sections")
    for section in section_register.values():
        log.debug("sync section {}".format(section.name))
        db_section, new = DescriptionTableSection.objects.update_or_create(
            code=section.id,
            defaults=dict(
                order=section.order,
                name=section.name,
                description=section.description,
            ),
        )
        if new:
            log.info("created section {}".format(section.name))
        else:
            log.info("updated section {}".format(section.name))

    sections = set(section_register.keys())

    log.info("sync table and field descriptions to db_meta tables")

    app_models = [model for model in apps.get_models() if callable(model) and issubclass(model, dj_models.Model)]  # NOQA

    relations = []
    tables = []

    has_error = False

    for model in app_models:
        if model._meta.abstract:
            log.debug("skipped {}".format(model._meta.verbose_name))
            continue
        log.debug("sync {}".format(model._meta.verbose_name))

        td = getattr(model, "TableDescription", object)
        section = getattr(td, "section", None)

        if (
            section is not None
            and (isinstance(section, str) and section not in sections)
            or (isinstance(section, TableSection) and section.id not in sections)
        ):
            log.error(f"section {section} not found (used in table {model.__name__})")
            has_error = True
            continue

        modules = get_modules_string(getattr(td, "modules", "*"))
        with_history = getattr(td, "with_history", False)

        table, new = DescriptionTable.objects.update_or_create(
            id=model._meta.db_table,
            defaults=dict(
                section_id=section.id if isinstance(section, TableSection) else section,
                order=getattr(td, "order", -1),
                model=model.__name__,
                name=model._meta.verbose_name,
                name_plural=model._meta.verbose_name_plural,
                description=getattr(td, "description", None),
                table_type_id=getattr(td, "table_type", None),
                modules=modules,
                with_history=getattr(td, "with_history", False),
            ),
        )

        tables.append(model._meta.db_table)

        if new:
            log.info("created {}".format(model._meta.verbose_name))
        else:
            log.info("updated {}".format(model._meta.verbose_name))

        field_sections = []
        for i, field in enumerate(model._meta.fields):
            config: Config = getattr(field, "r_config", None)
            if config is None:
                config = Config()

            field_section_instance = None
            if config.section is not None:
                i += config.section.order * 100

                if config.section not in field_sections:
                    field_section_instance, new = DescriptionFieldSection.objects.update_or_create(
                        table=table,
                        code=config.section.id,
                        defaults=dict(
                            name=config.section.name,
                            order=config.section.order,
                            # description=config.section.description
                        ),
                    )
                    i += 1000 * config.section.order

            default_value = getattr(field, "default_value", config.default_function)
            if getattr(field, "db_default") != dj_models.fields.NOT_PROVIDED:
                default_value = getattr(field, "db_default")

            field_desc, new = DescriptionField.objects.update_or_create(
                table=table,
                column_name=field.column,
                defaults=dict(
                    order=i,
                    field_type=field.get_internal_type(),
                    max_length=field.max_length,
                    nullable=field.null,
                    precision=config.precision,
                    is_relation=field.is_relation,
                    # relation_model_id=field.related_model if field.is_relation else None,
                    field_section=field_section_instance,
                    verbose_name=field.verbose_name,
                    dbf_name=config.dbf_name,
                    doc_unit=config.doc_unit,
                    doc_short=config.doc_short,
                    doc_full=config.doc_full,
                    doc_constraint=config.doc_constraint,
                    doc_development=config.doc_development,
                    calc_by=config.calculated_by,
                    default_value=default_value,
                    with_history=False if config.ignore_for_history else with_history,
                    modules=get_modules_string(config.modules) if config.modules else modules,
                    import_mode_id=config.import_mode,
                    export=config.export,
                ),
            )
            if config.calculation_input_for:
                for calc_id in config.calculation_input_for:
                    DescriptionFieldInputForCalc.objects.get_or_create(
                        calc_id=calc_id,
                        field=field_desc,
                    )

            if field.is_relation:
                relations.append((field_desc, field.related_model._meta.db_table))

    for field_desc, related_db_table in relations:
        if related_db_table not in tables:
            log.warning("relation table {} not found".format(related_db_table))
            continue
        field_desc.relation_table = DescriptionTable.objects.get(id=related_db_table)
        field_desc.save()

    if has_error:
        raise Exception("errors during processing, check logs for details")


if __name__ == "__main__":
    sync_db_meta_tables()
