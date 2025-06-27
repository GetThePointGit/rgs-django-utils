import logging

from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models.enums import BaseEnumExtended

from .enum_sections import section_enum_base

log = logging.getLogger(__name__)


class EnumModuleBase(BaseEnumExtended):
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
        abstract = True
        verbose_name = "module"
        verbose_name_plural = "modules"

    class TableDescription:
        is_extended_enum = True

        section = section_enum_base
        description = "De modules binnen applicatie"
        modules = "*"

    @classmethod
    def get_permissions(cls):
        no_filt = {}  # authenitcation module must be able to see all users

        return models.TPerm(
            public={
                "select": no_filt,
            },
            user_self={
                "select": no_filt,
            },
        )
