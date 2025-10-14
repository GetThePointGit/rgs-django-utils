from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models.enums import BaseEnumExtended

from .enum_sections import section_enum_auth

# todo: application specific roles should be moved to application specific code?!


class EnumRole(BaseEnumExtended):
    # roles use in hasura permission
    # general staff roles
    DEVELOPER_MANAGER = "dev_man"
    DEVELOPER = "dev"
    APPLICATION_MANAGER = "sys_adm"

    # organisation
    ORGANIZATION_ADMIN = "org_adm"
    ORGANIZATION_USER_ADMIN = "org_uman"
    ORGANIZATION_MEMBER = "org_mem"

    # project
    PROJECT_MANAGER = "proj_man"
    PROJECT_EMPLOYEE = "proj_coll"
    PROJECT_FIELDWORKER = "proj_fw"
    PROJECT_OBSERVER_INTERNAL = "proj_read"
    PROJECT_CLIENT = "proj_cli"
    PROJECT_CONTRACTOR = "proj_con"
    PROJECT_OBSERVER_EXTERNAL = "proj_ext"

    # special roles
    USER_SELF = "user_self"  # special role to identify the user himself
    AUTHENTICATED = "auth"  # special role to identify all authenticated users
    PUBLIC = "public"  # special role to identify all users, also not authenticated

    for_staff = models.BooleanField(
        "Voor superuser",
        default=False,
        config=models.Config(
            doc_short="Voor superuser",
            permissions=models.FPerm("-s-"),
        ),
    )
    for_org = models.BooleanField(
        "Voor organisatie",
        default=False,
        config=models.Config(
            doc_short="Voor organisatie",
            permissions=models.FPerm("-s-"),
        ),
    )
    for_project = models.BooleanField(
        "Voor project",
        default=False,
        config=models.Config(
            doc_short="Voor project",
            permissions=models.FPerm("-s-"),
        ),
    )

    order = models.IntegerField(
        "volgorde",
        default=0,
        config=models.Config(
            doc_short="Volgorde van de rollen",
            permissions=models.FPerm("-s-"),
        ),
    )
    description = models.TextField(
        "omschrijving",
        config=models.Config(
            doc_short="Omschrijving van de rol",
            permissions=models.FPerm("-s-"),
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
                {
                    "id": cls.DEVELOPER_MANAGER,
                    "name": "Developer manager",
                    "order": 0,
                    "for_staff": True,
                    "for_org": False,
                    "for_project": False,
                    "description": "Heeft alle rechten (voor de organisaties zonder restricties). Kan ook rechten van developers instellen.",
                },
                {
                    "id": cls.DEVELOPER,
                    "name": "Developer",
                    "order": 1,
                    "for_staff": True,
                    "for_org": False,
                    "for_project": False,
                    "description": "Heeft alle rechten (voor de organisaties zonder restricties)",
                },
                {
                    "id": cls.APPLICATION_MANAGER,
                    "name": "Applicatie manager",
                    "order": 2,
                    "for_staff": True,
                    "for_org": False,
                    "for_project": False,
                    "description": "Heeft alle rechten",
                },
                {
                    "id": cls.ORGANIZATION_ADMIN,
                    "name": "Organisatie admin",
                    "order": 3,
                    "for_staff": False,
                    "for_org": True,
                    "for_project": False,
                    "description": "Heeft alle rechten binnen de organisatie",
                },
                {
                    "id": cls.ORGANIZATION_USER_ADMIN,
                    "name": "Organisatie gebruikersbeheerder",
                    "order": 4,
                    "for_staff": False,
                    "for_org": True,
                    "for_project": False,
                    "description": "Mag gebruikers beheren van de organisatie",
                },
                {
                    "id": cls.ORGANIZATION_MEMBER,
                    "name": "Organisatie lid",
                    "order": 5,
                    "for_staff": False,
                    "for_org": True,
                    "for_project": False,
                    "description": "Is lid van de organisatie",
                },
                {
                    "id": cls.PROJECT_MANAGER,
                    "name": "Project manager",
                    "order": 6,
                    "for_staff": False,
                    "for_org": False,
                    "for_project": True,
                    "description": "Mag projecten beheren",
                },
                {
                    "id": cls.PROJECT_EMPLOYEE,
                    "name": "Project medewerker",
                    "order": 7,
                    "for_staff": False,
                    "for_org": False,
                    "for_project": True,
                    "description": "Is medewerker van het project",
                },
                {
                    "id": cls.PROJECT_FIELDWORKER,
                    "name": "Project veldwerker",
                    "order": 8,
                    "for_staff": False,
                    "for_org": False,
                    "for_project": True,
                    "description": "Is veldwerker van het project",
                },
                {
                    "id": cls.PROJECT_OBSERVER_INTERNAL,
                    "name": "Project meekijker intern",
                    "order": 9,
                    "for_staff": False,
                    "for_org": False,
                    "for_project": True,
                    "description": "Mag meekijken in het project (intern)",
                },
                {
                    "id": cls.PROJECT_CLIENT,
                    "name": "Project klant",
                    "order": 10,
                    "for_staff": False,
                    "for_org": False,
                    "for_project": True,
                    "description": "Is klant van het project",
                },
                {
                    "id": cls.PROJECT_CONTRACTOR,
                    "name": "Project aannemer",
                    "order": 11,
                    "for_staff": False,
                    "for_org": False,
                    "for_project": True,
                    "description": "Is aannemer van het project",
                },
                {
                    "id": cls.PROJECT_OBSERVER_EXTERNAL,
                    "name": "Project meekijker extern",
                    "order": 12,
                    "for_staff": False,
                    "for_org": False,
                    "for_project": True,
                    "description": "Mag meekijken in het project (extern)",
                },
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
