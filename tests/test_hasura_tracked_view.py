"""Tests voor ``HasuraTrackedView.all()`` (utils#59).

``all()`` gaf een set terug; de iteratievolgorde daarvan verschilt per proces
omdat de hash van een klasse op het geheugenadres is gebaseerd. De exports die
erover itereren (JSON-schema, Hasura-metadata, view-installatie) wisselden
daardoor van volgorde. Geen Django-DB nodig: de registratie loopt via
``__init_subclass__``.
"""

from unittest import TestCase as UnitTestCase

from rgs_django_utils.models.views import abstract
from rgs_django_utils.models.views.abstract import HasuraTrackedView


def _maak_view(naam: str, module: str) -> type[HasuraTrackedView]:
    """Maak een minimale, niet-abstracte subklasse met een opgegeven module-naam.

    Parameters
    ----------
    naam : str
        Klassenaam (``__qualname__``).
    module : str
        Waarde voor ``__module__``; bepaalt mee de sorteervolgorde.

    Returns
    -------
    type[HasuraTrackedView]
        De nieuwe subklasse; ``__init_subclass__`` heeft hem al geregistreerd.
    """

    class _View(HasuraTrackedView):
        @property
        def fields_referencing_original_table(self):
            return []

        @classmethod
        def get_all_views(cls, app_models=None):
            return []

        def get_sql(self) -> str:
            return ""

    _View.__name__ = naam
    _View.__qualname__ = naam
    _View.__module__ = module
    return _View


class TestHasuraTrackedViewAll(UnitTestCase):
    """Volgorde en ontdubbeling van ``HasuraTrackedView.all()``."""

    def setUp(self):
        self._registratie_vooraf = list(abstract.all)
        # Bewust in "verkeerde" volgorde aangemaakt: registratievolgorde ≠ sorteervolgorde.
        self.z_view = _maak_view("ZView", "tests.mod_a")
        self.a_view_mod_b = _maak_view("AView", "tests.mod_b")
        self.a_view_mod_a = _maak_view("AView", "tests.mod_a")

    def tearDown(self):
        # Registratie terugzetten zodat andere tests de testklassen niet zien.
        abstract.all[:] = self._registratie_vooraf

    def test_geeft_lijst_terug(self):
        self.assertIsInstance(HasuraTrackedView.all(), list, "all() moet een lijst zijn, geen set")

    def test_sorteert_op_module_en_qualname(self):
        eigen = [cls for cls in HasuraTrackedView.all() if cls in (self.z_view, self.a_view_mod_b, self.a_view_mod_a)]
        self.assertEqual(
            eigen,
            [self.a_view_mod_a, self.z_view, self.a_view_mod_b],
            "Volgorde moet (module, qualname) zijn, los van de registratievolgorde",
        )

    def test_ontdubbelt_dubbele_registraties(self):
        abstract.all.append(self.z_view)
        abstract.all.append(self.z_view)
        self.assertEqual(HasuraTrackedView.all().count(self.z_view), 1, "Een klasse mag maar één keer voorkomen")

    def test_volgorde_is_onafhankelijk_van_registratievolgorde(self):
        volgorde_1 = HasuraTrackedView.all()
        abstract.all.reverse()
        volgorde_2 = HasuraTrackedView.all()
        self.assertEqual(volgorde_1, volgorde_2, "Omgekeerde registratie mag de uitkomst niet veranderen")
