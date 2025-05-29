from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models.enums import BaseEnum

from ._enum_sections import section_enum_task


class EnumImportMode(BaseEnum):
    NOT_ALLOWED = "not_allowed"
    ALL = "all"
    CREATE_ONLY = "create"
    UPDATE_ONLY = "update"

    class Meta:
        db_table = "enum_import_mode"
        verbose_name = "import mode"
        verbose_name_plural = "import modes"

    class TableDescription:
        section = section_enum_task
        description = "Import mode (all, create only, update only) for db description"
        modules = "*"
        table_type = models.TableType.ENUM

    @classmethod
    def default_records(cls):
        return dict(
            fields=["id", "name"],
            data=[
                (cls.NOT_ALLOWED, "Not allowed"),
                (cls.ALL, "All"),
                (cls.CREATE_ONLY, "Create only"),
                (cls.UPDATE_ONLY, "Update only"),
            ],
        )

    @classmethod
    def permissions(cls):
        no_filt = {}  # authenitcation module must be able to see all users

        return models.TPerm(
            public={
                "select": no_filt,
            },
            user_self={
                "select": no_filt,
            },
        )
