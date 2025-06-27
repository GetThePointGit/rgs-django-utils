from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models.enums import BaseEnumExtended

from .enum_sections import section_enum_auth

# todo: move extended version to core, keep only generic part here


class EnumRole(BaseEnumExtended):
    # general staff roles
    DEVELOPER = "developer"
    APPLICATION_MANAGER = "appl_manager"
    APPLICATION_ADMIN = "appl_admin"

    # organisation
    ORGANISATION_ADMIN = "org_admin"
    ORGANISATION_USER_ADMIN = "org_user_admin"
    ORGANISATION_PROJECT_ADMIN = "org_proj_admin"
    ORGANISATION_MEMBER = "org_member"

    # project
    PROJECT_ADMIN = "proj_admin"
    PROJECT_MEMBER = "proj_member"
    PROJECT_OBSERVER = "proj_observer"
    PROJECT_OBSERVER_APPROVED = "proj_observer_approved"

    for_staff = models.BooleanField(
        "Voor superuser",
        default=False,
        config=models.Config(
            doc_short="Voor superuser",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    for_org = models.BooleanField(
        "Voor organisatie",
        default=False,
        config=models.Config(
            doc_short="Voor organisatie",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    for_project = models.BooleanField(
        "Voor project",
        default=False,
        config=models.Config(
            doc_short="Voor project",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    order = models.IntegerField(
        "volgorde",
        default=0,
        config=models.Config(
            doc_short="Volgorde van de rollen",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    description = models.TextField(
        "omschrijving",
        config=models.Config(
            doc_short="Omschrijving van de rol",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "enum_role"
        verbose_name = "Gebruikersrol"
        verbose_name_plural = "Gebruikersrollen"

    class TableDescription:
        section = section_enum_auth
        description = "De gebruikersrollen voor staf, organisaties en projecten"
        modules = "*"

    @classmethod
    def default_records(cls):
        return {
            "fields": ["id", "name", "order", "for_staff", "for_org", "for_project", "description"],
            "data": [
                (
                    cls.DEVELOPER,
                    "Ontwikkelaar",
                    1,
                    True,
                    False,
                    False,
                    "Heeft alle rechten (voor de organisaties zonder restricties)",
                ),
                (cls.APPLICATION_MANAGER, "Applicatie manager", 2, True, False, False, "Heeft alle rechten"),
                (
                    cls.APPLICATION_ADMIN,
                    "Applicatie admin",
                    3,
                    True,
                    False,
                    False,
                    "Heeft alle admin (organisatie + project) rechten (voor de organisaties zonder restricties)",
                ),
                (
                    cls.ORGANISATION_ADMIN,
                    "Organisatie admin",
                    4,
                    False,
                    True,
                    False,
                    "Heeft alle rechten binnen de organisatie",
                ),
                (
                    cls.ORGANISATION_USER_ADMIN,
                    "Organisatie gebruikersbeheerder",
                    5,
                    False,
                    True,
                    False,
                    "Mag gebruikers beheren van de organisatie",
                ),
                (
                    cls.ORGANISATION_PROJECT_ADMIN,
                    "Organisatie project admin",
                    6,
                    False,
                    True,
                    False,
                    "Mag projecten beheren van de organisatie",
                ),
                (cls.ORGANISATION_MEMBER, "Organisatie lid", 7, False, True, False, "Is lid van de organisatie"),
                (cls.PROJECT_ADMIN, "Project admin", 8, False, False, True, "Mag project beheren"),
                (cls.PROJECT_MEMBER, "Project lid", 9, False, False, True, "Is lid van het project"),
                (cls.PROJECT_OBSERVER, "Project meekijker", 10, False, False, True, "Mag meekijken in het project"),
                (
                    cls.PROJECT_OBSERVER_APPROVED,
                    "Project meekijker goedgekeurd",
                    11,
                    False,
                    False,
                    True,
                    "Mag meekijken in het project (goedgekeurd)",
                ),
            ],
        }

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
