import logging

from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models.enums import BaseEnumExtended

from .enum_sections import section_enum_base

log = logging.getLogger(__name__)


class EnumModule(BaseEnumExtended):
    """Enum for modules"""

    order = models.IntegerField(
        config=models.Config(
            doc_short="Volgorde van de modules",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    available = models.BooleanField(
        default=True,
        config=models.Config(
            doc_short="Is de module beschikbaar",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    # todo: add extra fields with configuration

    class Meta:
        db_table = "enum_module"
        verbose_name = "module"
        verbose_name_plural = "modules"

    class TableDescription:
        is_extended_enum = True

        section = section_enum_base
        description = "De modules binnen WIT"
        modules = "*"

    @classmethod
    def default_records(cls):
        from django.conf import settings

        modules = getattr(settings, "AVAILABLE_MODULES", [])

        if not modules:
            log.warn("No available modules found in settings.AVAILABLE_MODULES")

        return dict(
            fields=["id", "name", "order", "available"],
            data=[
                (module["id"], module["name"], index + 1, module["available"]) for index, module in enumerate(modules)
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
