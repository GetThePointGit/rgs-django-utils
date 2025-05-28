from rgs_utils.database import dj_extended_models as models
from rgs_utils.database.base_models.enums import BaseEnumExtended


class EnumAuthMethod(BaseEnumExtended):
    """Enum for authentication methods."""

    # USERNAME_PASSWORD = 'UP'
    EMAIL_PASSWORD = "email_password"
    EMAIL_PASSWORD_TOKEN = "email_password_token"
    PASSWORDLESS = "passwordless"
    PASSWORDLESS_TOKEN = "passwordless_token"
    GOOGLE = "google"
    MICROSOFT = "microsoft_entra_id"
    APPLE = "apple"

    order = models.IntegerField(
        "volgorde",
        config=models.Config(
            doc_short="Volgorde in selectielijsten",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    available = models.BooleanField(
        "beschikbaar",
        default=False,
        config=models.Config(
            doc_short="Is deze methode beschikbaar of nog in ontwikkeling",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    extra_costs = models.BooleanField(
        "extra kosten",
        config=models.Config(
            doc_short="Gebruik van deze methode kost extra geld",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    am_note = models.TextField(
        "notities applicatie/ontwikkelaars",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Notities voor de ontwikkelaars",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "enum_auth_method"
        verbose_name = "authenticatie methode"
        verbose_name_plural = "authenticatie methoden"

    class TableDescription:
        section = "enum_permission"
        order = 10
        modules = "*"

    @classmethod
    def default_records(cls):
        return dict(
            fields=["id", "name", "order", "available", "extra_costs", "am_note"],
            data=[
                # (cls.USERNAME_PASSWORD, 'Gebruikersnaam en wachtwoord', 1, True, False, False, None),
                (cls.EMAIL_PASSWORD, "e-mail en wachtwoord", 2, True, False, "1-factor, In ontwikkeling"),
                (
                    cls.EMAIL_PASSWORD_TOKEN,
                    "e-mail, wachtwoord en eenmalige wachtwoordcode",
                    2,
                    True,
                    True,
                    "2-factor, In ontwikkeling",
                ),
                (cls.PASSWORDLESS, "wachtwoordloos (magic link/ otp)", 3, False, False, "1-factor, In ontwikkeling"),
                (
                    cls.PASSWORDLESS_TOKEN,
                    "wachtwoordloos (magic link/ otp) met eenmalige wachtwoordcode",
                    2,
                    True,
                    True,
                    "2 factor, In ontwikkeling",
                ),
                (cls.GOOGLE, "Google", 4, False, True, "Organisatie, In ontwikkeling"),
                (cls.MICROSOFT, "Microsoft-entra-id", 5, True, True, "Organisatie"),
                (cls.APPLE, "Apple", 6, False, True, "Organisatie, In ontwikkeling"),
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
