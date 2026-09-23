"""Tests for ``get_modules_string`` (positional module mask)."""

from django.test import SimpleTestCase, override_settings

from rgs_django_utils.commands.sync_db_description import get_modules_string

MODULES = [
    {"id": "D", "name": "Database", "available": True},
    {"id": "P", "name": "Meerjarenplanning", "available": True},
    {"id": "V", "name": "Projecten", "available": False},
    {"id": "O", "name": "Oevers", "available": True},
]


@override_settings(AVAILABLE_MODULES=MODULES)
class TestGetModulesString(SimpleTestCase):
    """The mask keeps the order of ``settings.AVAILABLE_MODULES``."""

    def test_ster_geeft_alle_modules(self):
        """``"*"`` turns every slot on."""
        self.assertEqual(get_modules_string("*"), "DPVO")

    def test_enkele_module_als_string(self):
        """A single id keeps its own position and blanks the rest."""
        self.assertEqual(get_modules_string("D"), "D...")
        self.assertEqual(get_modules_string("O"), "...O")

    def test_meerdere_modules_als_string(self):
        """A string with several ids turns on exactly those slots."""
        self.assertEqual(get_modules_string("DO"), "D..O")

    def test_iterable_van_ids(self):
        """A list or tuple of ids gives the same result as the string form."""
        self.assertEqual(get_modules_string(["D", "O"]), "D..O")
        self.assertEqual(get_modules_string(("P",)), ".P..")

    def test_volgorde_van_invoer_doet_er_niet_toe(self):
        """The mask is positional, so the order of the input is irrelevant."""
        self.assertEqual(get_modules_string(["O", "D"]), get_modules_string(["D", "O"]))

    def test_enum_constanten(self):
        """Enum constants are ``str`` subclasses and work directly."""

        class EnumModule(str):
            pass

        self.assertEqual(get_modules_string([EnumModule("D"), EnumModule("O")]), "D..O")

    def test_onbekende_module_geeft_valueerror(self):
        """An unknown id is a configuration error, not a silently empty mask."""
        with self.assertRaises(ValueError):
            get_modules_string("X")
        with self.assertRaises(ValueError):
            get_modules_string(["D", "X"])

    def test_lege_invoer(self):
        """No modules means: no slot on."""
        self.assertEqual(get_modules_string([]), "....")


class TestGetModulesStringVolgtSettings(SimpleTestCase):
    """The mask is read from the settings per call, not at import time."""

    @override_settings(AVAILABLE_MODULES=[{"id": "D"}, {"id": "P"}])
    def test_volgt_gewijzigde_settings(self):
        """Other ``AVAILABLE_MODULES`` means a different mask, in the same process."""
        self.assertEqual(get_modules_string("*"), "DP")
        self.assertEqual(get_modules_string("P"), ".P")
