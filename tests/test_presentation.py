"""Tests for the Presentation field-layer object on Config."""

from unittest import TestCase as UnitTestCase

from rgs_django_utils.database.dj_extended_models import Config, Presentation


class TestPresentation(UnitTestCase):
    def test_defaults(self):
        p = Presentation()
        self.assertIsNone(p.width, "width default is None (geen tabelkolom by default)")
        self.assertFalse(p.bulk_edit, "bulk_edit default is False")
        self.assertFalse(p.map_label, "map_label default is False")
        self.assertIsNone(p.kind, "kind default is None")
        self.assertTrue(p.thousands_separator, "thousands_separator default is True")

    def test_kind_only_accepts_known_values(self):
        Presentation(kind="year")
        with self.assertRaises(ValueError):
            Presentation(kind="jaar")

    def test_width_must_be_positive_int(self):
        with self.assertRaises(ValueError):
            Presentation(width=0)
        with self.assertRaises(ValueError):
            Presentation(width=12.5)

    def test_config_stores_presentation(self):
        p = Presentation(width=100, bulk_edit=True)
        cfg = Config(presentation=p)
        self.assertIs(cfg.presentation, p)

    def test_config_presentation_defaults_to_none(self):
        self.assertIsNone(Config().presentation)

    def test_repr_is_readable(self):
        self.assertEqual(
            repr(Presentation(width=100, bulk_edit=True)),
            "Presentation(width=100, bulk_edit=True, map_label=False, kind=None, thousands_separator=True)",
        )
