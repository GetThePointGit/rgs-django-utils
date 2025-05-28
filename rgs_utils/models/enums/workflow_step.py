from rgs_utils.database import dj_extended_models as models
from rgs_utils.database.base_models.enums import BaseEnumExtended

from ._enum_sections import section_enum_task


class EnumWorkflowStep(BaseEnumExtended):
    DEFAULT = "default"
    SOURCE_SELECTION = "source_selection"
    IMPORT_CONFIGURATION = "import_configuration"
    FIELDS_CONFIGURATION = "fields_configuration"
    VALIDATION = "validation"
    APPROVAL = "approval"
    CHECK = "check"
    IMPORT = "import"

    order = models.IntegerField(
        verbose_name="volgorde",
        default=0,
        config=models.Config(
            doc_short="Volgorde van de stappen",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    action = models.TextField(
        verbose_name="actie",
        default="",
        config=models.Config(
            doc_short="Actie - wordt gebruikt in de UI",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    for_import = models.BooleanField(
        verbose_name="Voor import",
        default=False,
        config=models.Config(
            doc_short="Voor import",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    for_export = models.BooleanField(
        verbose_name="Voor export",
        default=False,
        config=models.Config(
            doc_short="Voor export",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    for_processing = models.BooleanField(
        verbose_name="Voor processing",
        default=False,
        config=models.Config(
            doc_short="Voor processing",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "enum_workflow_step"
        verbose_name = "Workflow stap"
        verbose_name_plural = "workflow stappen"

    class TableDescription:
        section = section_enum_task
        description = "De stappen van het import/export/verwerking proces"
        modules = "*"

    @classmethod
    def default_records(cls):
        return dict(
            fields=["id", "name", "order", "action", "for_import", "for_export", "for_processing"],
            data=[
                (cls.DEFAULT, "default", 0, "", False, True, True),
                (cls.SOURCE_SELECTION, "bron selectie", 1, "opslaan", True, False, False),
                (cls.IMPORT_CONFIGURATION, "import configureren", 2, "opslaan en verwerken", True, False, False),
                (cls.FIELDS_CONFIGURATION, "velden configureren", 3, "opslaan en verwerken", True, False, False),
                (cls.VALIDATION, "valideren", 4, "doorgaan", True, False, False),
                (cls.APPROVAL, "goedkeuren", 5, "importeren", True, False, False),
                (cls.IMPORT, "importeren", 6, "", True, False, False),
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
