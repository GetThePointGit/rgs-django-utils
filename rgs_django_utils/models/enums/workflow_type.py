from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models.enums import BaseEnum

from ._enum_sections import section_enum_task


class EnumWorkflowType(BaseEnum):
    EXPORT = "export"
    IMPORT = "import"
    PROCESSING = "processing"

    class Meta:
        db_table = "enum_workflow_type"
        verbose_name = "workflow type"
        verbose_name_plural = "workflow types"

    class TableDescription:
        section = section_enum_task
        description = "De types van taken (import, export, processing)"
        modules = "*"
        table_type = models.TableType.ENUM

    @classmethod
    def default_records(cls):
        return dict(
            fields=["id", "name"],
            data=[
                (cls.EXPORT, "export"),
                (cls.IMPORT, "import"),
                (cls.PROCESSING, "processing"),
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
