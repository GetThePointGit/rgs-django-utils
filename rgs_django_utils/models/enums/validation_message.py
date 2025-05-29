import logging
import os

from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models.enums import BaseEnumExtended


class EnumValidationMessage(BaseEnumExtended):
    """Enum for error and warningmessages in calculations."""

    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

    level = models.IntegerField(
        config=models.Config(
            doc_short="Niveau van de melding",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    message = models.TextField(
        config=models.Config(
            doc_short="Melding",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "enum_validation_msg"
        verbose_name = "Validatiemelding"
        verbose_name_plural = "Validatiemeldingen"

    class TableDescription:
        section = "enum_validation"
        order = 10
        modules = "*"

    @classmethod
    def default_records(cls):
        from django.apps import apps
        from rgs_django_utils.tasks.validation_baseclass import _registered_classes

        # load for all django apps the tasks classes
        for name, app in apps.app_configs.items():
            app_path = app.module.__path__[0]
            tasks_path = os.path.join(app_path, "tasks", "validation_msg")

            if os.path.isdir(tasks_path) or os.path.isfile(tasks_path + ".py"):
                __import__(f"{app.name}.tasks.validation_msg")

        data = []
        for mods in _registered_classes.values():
            data.append(
                (
                    mods.IDENTIFIER,
                    mods.NAME,
                    mods.LEVEL,
                    mods.MESSAGE,
                )
            )

        return dict(
            fields=["id", "name", "level", "message"],
            data=data,
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


# code foutmelding	nieuw label	wat ontbreekt
# watergangen
# 80	Watergang bevat geen profiel en geen representatieve hoeveelheid.	profiel, rep. hoeveelheid
# 81	Watergang niet gekoppeld aan baggercluster.	baggercluster
# 82	Watergang bevat geen profiel, WIT rekent met representatieve hoeveelheid.	profiel
# 83	Watergang bevat geen profiel en geen representatieve hoeveelheid.	profiel, rep. hoeveelheid
# 84	Watergang bevat geen profiel, WIT rekent met representatieve hoeveelheid.	profiel
# 85	Watergang heeft geen lengte.	waterganglengte
# profielen
# 401	Geen profielmeting.	profielmeting
# 402	Geen profielmeting.	profielmeting
# 403	Geen profielmeting.	profielmeting
# 701	Geen profielmeting.	profielmeting
# 702	Profiel heeft geen representatieve lengte.	representatieve lengte
# 703	Profiel niet gekoppeld aan legger.	legger
# 704	Profiel niet gekoppeld aan watergang.	koppeling watergang
# 705	Profiel niet gekoppeld aan monstervak.	koppeling monstervak
# 706	Monstervak bevat geen kwaliteit.	kwaliteit binnen monstervak
# 707	Baggerbestemming bevat geen kosten voor bestemming XXX.	kosten bestemming XXX
# 708	Watergang niet gekoppeld aan baggermethode.	baggermethode
# 709	Watergang niet gekoppeld aan baggerbestemming.	baggerbestemming
# 731	Geen profielmeting.	profielmeting
# 732	Profiel heeft geen representatieve lengte.	representatieve lengte
# 733	Profiel bevat geen legger.	legger
# 1401	Geen profielmeting.	profielmeting
# 1402	Geen profielmeting.	profielmeting
# 1403	Profiel heeft geen geometrie.	geometrie profiel
# 1501	Watergang is niet één lijnstuk.	watergang niet één lijnstuk
# 7091	Watergang bevat geen aanwascijfer.	aanwascijfer
# 7092	Watergang bevat geen aanwascijfer.	aanwascijfer
# 7093	Watergang bevat geen recente profielmeting.	recente meting
#
# Ontbrekende fouten in berekening baggerhoeveelheden en -kosten WIT
# watergangen
# XXX	Watergang bevat geen geometrie.	geometrie watergang
# XXX	Watergang is niet één lijnstuk.	watergang niet één lijnstuk
# XXX	Watergang bevat geen legger.	legger
# XXX	Watergang niet gekoppeld aan baggermethode.	baggermethode
# XXX	Watergang niet gekoppeld aan baggerbestemming.	baggerbestemming
# XXX	Watergang bevat representatieve profielen uit WIT 2.	profielmeting
# XXX	Watergang bevat geen strategie slib.	strategie slib
# XXX	Strategie slib watergang kijkt naar legger, maar watergang bevat geen legger.	legger
# XXX	Baggercluster bevat geen gepland jaar van baggeren.	gepland jaar
# XXX	Baggercluster bevat verkeerd gepland jaar van baggeren.	gepland jaar

# default_records = dict(
#     fields=['element', 'id', 'template', ],
#     data=[
#         ('ww', 80, 'Watergang bevat geen actuele profiellocatie met meting en geen representatieve hoeveelheid.'),
#         ('ww', 81, 'Watergang niet gekoppeld aan baggercluster.'),
#
#         # ...
#     ]
# )
