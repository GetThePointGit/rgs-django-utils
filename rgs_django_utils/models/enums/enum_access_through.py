from rgs_django_utils.database.base_models.enums import BaseEnum

from .enum_sections import section_enum_base


class EnumAccessThrough(BaseEnum):
    """Authorisation scope — how a user inherits access to a record.

    Values line up with the ``upm`` (user-project mapping) table that
    carries per-user/project filters. ``public`` rows grant access to
    everyone; ``user`` rows bind access to a specific user id.
    """

    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    ORGANISATION = "organisation"
    PROJECT = "project"
    TEAM_MEMBER = "team_member"
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
                (cls.TEAM_MEMBER, "Toegang voor gebruikers binnen een team"),
                (cls.USER, "Toegang voor een specifieke gebruiker"),
            ],
        }
