"""Tests for rgs_django_utils.commands.export_datamodel_to_json_schema.

Covers the metadata-emission additions (unit, precision, docFull, modules)
and the modules-normalisation helper. Geen Django DB nodig — alle tests
werken op losse veld-instanties met handmatig geprikte Config.
"""

from unittest import TestCase as UnitTestCase

from django.db import models as dj_models

from rgs_django_utils.commands.export_datamodel_to_json_schema import (
    SchemaGenerator,
    _modules_to_list,
)
from rgs_django_utils.database.dj_extended_models import Config, ForeignKey


class TestModulesToList(UnitTestCase):
    """Pure-function test for the modules normalisation helper."""

    def test_none_returns_none(self):
        self.assertIsNone(_modules_to_list(None), "None moet None blijven")

    def test_wildcard_returns_none(self):
        self.assertIsNone(_modules_to_list("*"), "Wildcard moet None worden")

    def test_string_returns_singleton_list(self):
        self.assertEqual(_modules_to_list("mod_a"), ["mod_a"], "String moet singleton list worden")

    def test_list_of_strings_passthrough(self):
        self.assertEqual(_modules_to_list(["mod_a", "mod_b"]), ["mod_a", "mod_b"], "List of strings moet onveranderd blijven")

    def test_tuple_of_strings_returns_list(self):
        self.assertEqual(_modules_to_list(("a", "b")), ["a", "b"], "Tuple of strings moet list worden")

    def test_empty_iterable_returns_none(self):
        self.assertIsNone(_modules_to_list([]), "Lege iterable moet None worden")

    def test_non_iterable_returns_none(self):
        self.assertIsNone(_modules_to_list(123), "Niet-iterable moet None worden")

    def test_non_string_items_stringified(self):
        class _M:
            def __str__(self):
                return "module_x"

        self.assertEqual(_modules_to_list([_M(), _M()]), ["module_x", "module_x"], "Niet-string items moeten worden omgezet naar string")


def _bare_field(field_cls, name: str = "depth", **kwargs):
    """Construct a Django field with the minimum attributes used by the exporter.

    The exporter only reads introspection attributes; we side-step
    contribute_to_class so we do not need a registered model.
    """
    field = field_cls(**kwargs)
    field.name = name
    field.column = name
    return field


class TestFieldToPropertyMetadata(UnitTestCase):
    """Verify that the new Config metadata reaches the JSON Schema property."""

    def _gen(self):
        return SchemaGenerator(models=[])

    def test_unit_emitted_from_doc_unit(self):
        field = _bare_field(dj_models.FloatField)
        field.config = Config(doc_unit="m")
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["unit"], "m", "doc_unit moet worden omgezet naar unit in JSON Schema")

    def test_precision_emitted(self):
        field = _bare_field(dj_models.FloatField)
        field.config = Config(precision=2)
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["precision"], 2, "precision moet worden omgezet naar JSON Schema")

    def test_doc_full_emitted_as_docFull(self):
        field = _bare_field(dj_models.FloatField)
        field.config = Config(doc_full="Uitgebreide uitleg over diepte.")
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["docFull"], "Uitgebreide uitleg over diepte.", "doc_full moet worden omgezet naar docFull in JSON Schema")

    def test_modules_list_emitted(self):
        field = _bare_field(dj_models.IntegerField)
        field.config = Config(modules=["mod_a", "mod_b"])
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["modules"], ["mod_a", "mod_b"], "modules list moet worden omgezet naar JSON Schema")

    def test_modules_wildcard_not_emitted(self):
        field = _bare_field(dj_models.IntegerField)
        field.config = Config(modules="*")
        prop = self._gen()._field_to_property(field=field)
        self.assertNotIn("modules", prop, "Wildcard modules moeten niet worden opgenomen in JSON Schema")

    def test_no_metadata_keeps_property_clean(self):
        field = _bare_field(dj_models.FloatField)
        prop = self._gen()._field_to_property(field=field)
        for key in ("unit", "precision", "docFull", "modules"):
            self.assertNotIn(key, prop, f"{key} moet niet aanwezig zijn in JSON Schema wanneer er geen metadata is")

    def test_existing_keys_preserved(self):
        """Bestaande description (uit doc_short) blijft werken naast nieuwe keys."""
        field = _bare_field(dj_models.FloatField)
        field.config = Config(
            doc_short="diepte",
            doc_unit="m",
            precision=2,
            doc_full="lange uitleg",
        )
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["description"], "diepte", "doc_short moet worden omgezet naar description in JSON Schema")
        self.assertEqual(prop["unit"], "m", "doc_unit moet worden omgezet naar unit in JSON Schema")
        self.assertEqual(prop["precision"], 2, "precision moet worden omgezet naar JSON Schema")
        self.assertEqual(prop["docFull"], "lange uitleg", "doc_full moet worden omgezet naar docFull in JSON Schema")

    def test_precision_zero_emitted(self):
        """precision=0 is een geldige waarde en moet meekomen."""
        field = _bare_field(dj_models.IntegerField)
        field.config = Config(precision=0)
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["precision"], 0, "precision=0 moet worden opgenomen in JSON Schema")

    def test_r_config_is_read(self):
        """FieldConfig._init_extras stores Config as field.r_config; exporter must honour it."""
        field = _bare_field(dj_models.FloatField)
        field.r_config = Config(doc_unit="m", precision=2, doc_short="diepte")
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["unit"], "m", "doc_unit moet worden omgezet naar unit in JSON Schema")
        self.assertEqual(prop["precision"], 2, "precision moet worden omgezet naar JSON Schema")
        self.assertEqual(prop["description"], "diepte", "doc_short moet worden omgezet naar description in JSON Schema")

    def test_r_config_takes_precedence_over_config(self):
        """Wanneer beide bestaan, wint r_config (rgs-django-utils convention)."""
        field = _bare_field(dj_models.FloatField)
        field.r_config = Config(doc_unit="m")
        field.config = Config(doc_unit="kg")
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["unit"], "m", "doc_unit in r_config moet voorrang hebben boven doc_unit in config bij omzetting naar JSON Schema")

    def test_nullable_emitted(self):
        """required is een apart veld in JSON Schema, niet een attribuut van de property."""  # noqa: D403
        field = _bare_field(dj_models.FloatField, null=True)
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["type"], ["number", "null"], "type moet ['number', 'null'] zijn voor FloatField in JSON Schema")

        field = _bare_field(dj_models.FloatField, null=False)
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["type"], "number", "type moet 'number' zijn voor FloatField in JSON Schema")

    def test_foreign_key_to_enum_emits_one_of(self):
        """FK naar enum-model moet een oneOf met $ref naar enum-schema opleveren."""
        # Deze test is hier omdat het doc_unit-veld van Config alleen bij de property-emissie wordt gelezen.
        # De exporter moet nog steeds herkennen dat het veld een FK naar een enum is, ook als er Config op zit.
        from tests.testapp.models import EnumTestModel

        field = _bare_field(ForeignKey, to=EnumTestModel, on_delete=dj_models.CASCADE)
        field.config = Config(doc_unit="m")
        prop = self._gen()._field_to_property(field=field)
        self.assertIn("oneOf", prop, "oneOf moet aanwezig zijn in JSON Schema voor FK naar enum-model")
        self.assertEqual(len(prop["oneOf"]), 4, "oneOf moet 4 elementen bevatten in JSON Schema voor FK naar enum-model")
        self.assertEqual(prop["oneOf"][0], {'const': 'A_10', 'title': 'test enum 0'}, "Het eerste element van oneOf moet {'const': 'A_10', 'title': 'test enum 0'} zijn in JSON Schema")
        self.assertEqual(prop["oneOf"][1], {'const': 'A_11', 'title': 'test enum 1'}, "Het tweede element van oneOf moet {'const': 'A_11', 'title': 'test enum 1'} zijn in JSON Schema")
        self.assertEqual(prop["oneOf"][2], {'const': 'A_12', 'title': 'test enum 2'}, "Het derde element van oneOf moet {'const': 'A_12', 'title': 'test enum 2'} zijn in JSON Schema")
        self.assertEqual(prop["oneOf"][3], {'const': 'A_13', 'title': 'test enum 3'}, "Het vierde element van oneOf moet {'const': 'A_13', 'title': 'test enum 3'} zijn in JSON Schema")