from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models.enums import BaseEnumExtended

from ._enum_sections import section_enum_task


class EnumSourceType(BaseEnumExtended):
    WORKFLOW = "workflow"

    FILE = "file"
    PROJECT = "project"
    DATABASE = "database"
    REMOTE_API = "remote_api"

    INTERFACE = "interface"
    MOBIEL = "mobiel"
    EDIT_SESSIE_INTERFACE = "interface_edit_sessie"
    EDIT_SESSIE_MOBIEL = "mobiel_edit_sessie"

    order = models.IntegerField(
        verbose_name="volgorde",
        default=0,
        config=models.Config(
            doc_short="Volgorde van de bron types",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    for_import = models.BooleanField(
        verbose_name="Voor import",
        default=False,
        config=models.Config(
            doc_short="Volgorde van de bron types",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    for_export = models.BooleanField(
        verbose_name="Voor export",
        default=False,
        config=models.Config(
            doc_short="Volgorde van de bron types",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "enum_source_type"
        verbose_name = "Brontype"
        verbose_name_plural = "Brontypes"

    class TableDescription:
        section = section_enum_task
        description = "De verschillende bron types"
        modules = "*"

    @classmethod
    def default_records(cls):
        return {
            "fields": ["id", "name", "order", "for_import", "for_export"],
            "data": [
                (cls.FILE, "Bestand", 1, True, True),
                (cls.PROJECT, "Project", 2, True, True),
                (cls.DATABASE, "Database", 3, True, False),
                (cls.REMOTE_API, "Remote API", 4, True, True),
                (cls.WORKFLOW, "Workflow", 4, False, False),
                (cls.INTERFACE, "Interface", 5, False, False),
                (cls.MOBIEL, "Mobiel", 6, False, False),
                (cls.EDIT_SESSIE_INTERFACE, "Edit sessie interface", 7, False, False),
                (cls.EDIT_SESSIE_MOBIEL, "Edit sessie mobiel", 8, False, False),
            ],
        }

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
