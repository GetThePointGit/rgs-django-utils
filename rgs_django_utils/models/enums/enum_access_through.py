from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models.enums import BaseEnum

from .enum_sections import section_enum_base


class EnumAccessThrough(BaseEnum):
    """Enum for way authorization is linked."""

    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    ORGANISATION = "organisation"
    PROJECT = "project"
    USER_GROUP = "user_group"
    USER = "user"

    class Meta:
        db_table = "enum_access_through"
        verbose_name = "toegang via"
        verbose_name_plural = "toegang via"

    class TableDescription:
        section = section_enum_base

    @classmethod
    def default_records(cls):
        return {
            "fields": ["id", "name"],
            "data": [
                (cls.PUBLIC, "Toegang voor iedereen, ook zonder in te loggen"),
                (cls.AUTHENTICATED, "Toegang voor iedere ingelogde gebruiker"),
                (cls.ORGANISATION, "Toegang voor gebruikers binnen een organisatie"),
                (cls.PROJECT, "Toegang voor gebruikers binnen een project"),
                (cls.USER_GROUP, "Toegang voor gebruikers binnen een gebruikersgroep"),
                (cls.USER, "Toegang voor een specifieke gebruiker"),
            ],
        }
