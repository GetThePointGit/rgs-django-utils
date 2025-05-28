from rgs_utils.database import dj_extended_models as models
from rgs_utils.database.base_models.enums import BaseEnumExtended

from ._enum_sections import section_enum_task


class EnumTaskStatus(BaseEnumExtended):
    NOT_STARTED = "not_started"
    WAIT_FOR_USER_INPUT = "user_input"

    SCHEDULED = "scheduled"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"

    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    COMPLETED_WITH_ERRORS = "completed_with_errors"

    FAILED = "failed"
    CANCELLED = "cancelled"

    order = models.IntegerField(
        verbose_name="volgorde",
        default=0,
        config=models.Config(
            doc_short="Volgorde van de statussen",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "enum_task_status"
        verbose_name = "Taakstatus"
        verbose_name_plural = "Taakstatussen"

    class TableDescription:
        section = section_enum_task
        description = "De statussen die een taak (import, export, processing) kan hebben"
        modules = "*"

    @classmethod
    def default_records(cls):
        return dict(
            fields=["id", "name", "order"],
            data=[
                (cls.NOT_STARTED, "niet gestart", 0),
                (cls.WAIT_FOR_USER_INPUT, "wacht op input", 1),
                (cls.SCHEDULED, "gepland", 2),
                (cls.QUEUED, "in de wachtrij", 3),
                (cls.IN_PROGRESS, "bezig met verwerken", 4),
                (cls.COMPLETED, "succesvol afgerond", 5),
                (cls.COMPLETED_WITH_WARNINGS, "afgerond met (data) waarschuwingen", 6),
                (cls.COMPLETED_WITH_ERRORS, "afgerond met (data) errors", 7),
                (cls.FAILED, "mislukt", 8),
                (cls.CANCELLED, "geannuleerd", 9),
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
