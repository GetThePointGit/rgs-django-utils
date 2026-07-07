"""Tests for rgs_django_utils.commands.export_datamodel_to_json_schema.

Covers the metadata-emission additions (unit, precision, docFull, modules)
and the modules-normalisation helper. Geen Django DB nodig — alle tests
werken op losse veld-instanties met handmatig geprikte Config.
"""

from unittest import TestCase as UnitTestCase

from django.contrib.gis.db import models as base_models
from django.db import models as dj_models

from rgs_django_utils.commands.export_datamodel_to_json_schema import (
    SchemaGenerator,
    _modules_to_list,
)
from rgs_django_utils.database.dj_extended_models import Config, ForeignKey, ManyToManyField, OneToOneField


class TestModulesToList(UnitTestCase):
    """Pure-function test for the modules normalisation helper."""

    def test_none_returns_none(self):
        self.assertIsNone(_modules_to_list(None), "None moet None blijven")

    def test_wildcard_returns_none(self):
        self.assertIsNone(_modules_to_list("*"), "Wildcard moet None worden")

    def test_string_returns_singleton_list(self):
        self.assertEqual(_modules_to_list("mod_a"), ["mod_a"], "String moet singleton list worden")

    def test_list_of_strings_passthrough(self):
        self.assertEqual(
            _modules_to_list(["mod_a", "mod_b"]), ["mod_a", "mod_b"], "List of strings moet onveranderd blijven"
        )

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

        self.assertEqual(
            _modules_to_list([_M(), _M()]),
            ["module_x", "module_x"],
            "Niet-string items moeten worden omgezet naar string",
        )


def _bare_field(field_cls, name: str = "depth", **kwargs):
    """Construct a Django field with the minimum attributes used by the exporter.

    The exporter only reads introspection attributes; we side-step
    contribute_to_class so we do not need a registered model.
    """
    field = field_cls(**kwargs)
    field.name = name
    field.column = name
    return field


class OneToManyRelatedField(dj_models.ForeignKey):
    """Simuleert een 1-to-n relatie, waar Django zelf geen veld voor heeft.

    De exporter moet nog steeds herkennen dat dit een FK is en er een oneOf van maken.
    """

    def __init__(self, to, on_delete):
        super().__init__(to=to, on_delete=on_delete)

    one_to_many = True
    one_to_one = False
    many_to_one = False
    many_to_many = False


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
        self.assertEqual(
            prop["docFull"],
            "Uitgebreide uitleg over diepte.",
            "doc_full moet worden omgezet naar docFull in JSON Schema",
        )

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
        self.assertEqual(
            prop["description"], "diepte", "doc_short moet worden omgezet naar description in JSON Schema"
        )
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
        self.assertEqual(
            prop["description"], "diepte", "doc_short moet worden omgezet naar description in JSON Schema"
        )

    def test_r_config_takes_precedence_over_config(self):
        """Wanneer beide bestaan, wint r_config (rgs-django-utils convention)."""
        field = _bare_field(dj_models.FloatField)
        field.r_config = Config(doc_unit="m")
        field.config = Config(doc_unit="kg")
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(
            prop["unit"],
            "m",
            "doc_unit in r_config moet voorrang hebben boven doc_unit in config bij omzetting naar JSON Schema",
        )

    def test_nullable_emitted(self):
        """required is een apart veld in JSON Schema, niet een attribuut van de property."""  # noqa: D403
        field = _bare_field(dj_models.FloatField, null=True)
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(
            prop["type"], ["number", "null"], "type moet ['number', 'null'] zijn voor FloatField in JSON Schema"
        )

        field = _bare_field(dj_models.FloatField, null=False)
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["type"], "number", "type moet 'number' zijn voor FloatField in JSON Schema")

    def test_foreign_key_to_enum_emits_one_of(self):
        """FK naar enum-model moet een oneOf met $ref naar enum-schema opleveren."""
        # Deze test is hier omdat het doc_unit-veld van Config alleen bij de property-emissie wordt gelezen.
        # De exporter moet nog steeds herkennen dat het veld een FK naar een enum is, ook als er Config op zit.
        from tests.testapp.models import EnumTestModel

        field = _bare_field(ForeignKey, to=EnumTestModel, on_delete=dj_models.CASCADE)
        field.config = Config()
        prop = self._gen()._field_to_property(field=field)
        self.assertIn("oneOf", prop, "oneOf moet aanwezig zijn in JSON Schema voor FK naar enum-model")
        self.assertEqual(
            len(prop["oneOf"]), 4, "oneOf moet 4 elementen bevatten in JSON Schema voor FK naar enum-model"
        )
        self.assertEqual(
            prop["oneOf"][0],
            {"const": "A_10", "title": "test enum 0"},
            "Het eerste element van oneOf moet {'const': 'A_10', 'title': 'test enum 0'} zijn in JSON Schema",
        )
        self.assertEqual(
            prop["oneOf"][1],
            {"const": "A_11", "title": "test enum 1"},
            "Het tweede element van oneOf moet {'const': 'A_11', 'title': 'test enum 1'} zijn in JSON Schema",
        )
        self.assertEqual(
            prop["oneOf"][2],
            {"const": "A_12", "title": "test enum 2"},
            "Het derde element van oneOf moet {'const': 'A_12', 'title': 'test enum 2'} zijn in JSON Schema",
        )
        self.assertEqual(
            prop["oneOf"][3],
            {"const": "A_13", "title": "test enum 3"},
            "Het vierde element van oneOf moet {'const': 'A_13', 'title': 'test enum 3'} zijn in JSON Schema",
        )

        field = _bare_field(ForeignKey, to=EnumTestModel, on_delete=dj_models.CASCADE, null=True)
        field.config = Config()
        prop = self._gen()._field_to_property(field=field)
        self.assertIn("anyOf", prop, "anyOf moet aanwezig zijn in JSON Schema voor FK naar enum-model")
        self.assertEqual(
            len(prop["anyOf"]), 2, "anyOf moet 2 elementen bevatten in JSON Schema voor FK naar nullable enum-model"
        )
        self.assertEqual(
            len(prop["anyOf"][0]["oneOf"]),
            4,
            "Het eerste element van anyOf moet een oneOf bevatten met 4 elementen in JSON Schema voor FK naar nullable enum-model",
        )
        self.assertEqual(
            prop["anyOf"][0]["oneOf"][0],
            {"const": "A_10", "title": "test enum 0"},
            "Het eerste element van oneOf binnen anyOf moet {'const': 'A_10', 'title': 'test enum 0'} zijn in JSON Schema",
        )
        self.assertEqual(
            prop["anyOf"][0]["oneOf"][1],
            {"const": "A_11", "title": "test enum 1"},
            "Het tweede element van oneOf binnen anyOf moet {'const': 'A_11', 'title': 'test enum 1'} zijn in JSON Schema",
        )
        self.assertEqual(
            prop["anyOf"][0]["oneOf"][2],
            {"const": "A_12", "title": "test enum 2"},
            "Het derde element van oneOf binnen anyOf moet {'const': 'A_12', 'title': 'test enum 2'} zijn in JSON Schema",
        )
        self.assertEqual(
            prop["anyOf"][0]["oneOf"][3],
            {"const": "A_13", "title": "test enum 3"},
            "Het vierde element van oneOf binnen anyOf moet {'const': 'A_13', 'title': 'test enum 3'} zijn in JSON Schema",
        )
        self.assertEqual(
            prop["anyOf"][1],
            {"type": "null"},
            "Het tweede element van anyOf moet {'type': 'null'} zijn in JSON Schema",
        )

    def test_foreign_key_to_extended_enum_emits_ref(self):
        """FK naar extended enum-model moet een $ref naar het enum-schema opleveren, niet een oneOf."""
        from tests.testapp.models import EnumExtendedTestModel

        field = _bare_field(ForeignKey, to=EnumExtendedTestModel, on_delete=dj_models.CASCADE)
        field.config = Config()
        prop = self._gen()._field_to_property(field=field)
        self.assertIn("oneOf", prop, "oneOf moet aanwezig zijn in JSON Schema voor FK naar enum-model")
        self.assertEqual(
            len(prop["oneOf"]), 4, "oneOf moet 4 elementen bevatten in JSON Schema voor FK naar enum-model"
        )
        self.assertEqual(
            prop["oneOf"][0],
            {"const": "A_0", "title": "test0"},
            "Het eerste element van oneOf moet {'const': 'A_0', 'title': 'test0'} zijn in JSON Schema",
        )
        self.assertEqual(
            prop["oneOf"][1],
            {"const": "A_1", "title": "test1"},
            "Het tweede element van oneOf moet {'const': 'A_1', 'title': 'test1'} zijn in JSON Schema",
        )
        self.assertEqual(
            prop["oneOf"][2],
            {"const": "A_2", "title": "test2"},
            "Het derde element van oneOf moet {'const': 'A_2', 'title': 'test2'} zijn in JSON Schema",
        )
        self.assertEqual(
            prop["oneOf"][3],
            {"const": "A_3", "title": "test3"},
            "Het vierde element van oneOf moet {'const': 'A_3', 'title': 'test3'} zijn in JSON Schema",
        )

    def test_1_to_1_foreign_key_emits_ref(self):
        """1-to-1 FK moet een $ref naar het gerelateerde model opleveren, niet een oneOf."""
        from tests.testapp.models import MiddleModel

        field = _bare_field(OneToOneField, to=MiddleModel, on_delete=dj_models.CASCADE)
        field.config = Config()
        prop = self._gen()._field_to_property(field=field)
        self.assertIn("$ref", prop, "$ref moet aanwezig zijn in JSON Schema voor 1-to-1 FK")
        self.assertEqual(
            prop["$ref"],
            "#/$defs/testapp_middlemodel",
            "$ref moet '#/$defs/testapp_middlemodel' zijn in JSON Schema voor 1-to-1 FK",
        )

    def test_n_to_1_foreign_key_emits_ref(self):
        """n-to-1 FK moet een $ref naar het gerelateerde model opleveren, niet een oneOf."""
        from tests.testapp.models import MiddleModel

        field = _bare_field(ForeignKey, to=MiddleModel, on_delete=dj_models.CASCADE)
        field.config = Config()
        prop = self._gen()._field_to_property(field=field)
        self.assertIn("$ref", prop, "$ref moet aanwezig zijn in JSON Schema voor n-to-1 FK")
        self.assertEqual(
            prop["$ref"],
            "#/$defs/testapp_middlemodel",
            "$ref moet '#/$defs/testapp_middlemodel' zijn in JSON Schema voor n-to-1 FK",
        )

    def test_n_to_m_foreign_key_emits_array(self):
        """n-to-m FK moet een array met $ref naar het gerelateerde model opleveren."""
        from tests.testapp.models import MiddleModel

        field = _bare_field(ManyToManyField, to=MiddleModel)
        field.config = Config()
        prop = self._gen()._field_to_property(field=field)
        self.assertIn("type", prop, "type moet aanwezig zijn in JSON Schema voor n-to-m FK")
        self.assertEqual(prop["type"], "array", "type moet 'array' zijn in JSON Schema voor n-to-m FK")
        self.assertIn("items", prop, "items moet aanwezig zijn in JSON Schema voor n-to-m FK")
        self.assertIn("$ref", prop["items"], "$ref moet aanwezig zijn in items van JSON Schema voor n-to-m FK")
        self.assertEqual(
            prop["items"]["$ref"],
            "#/$defs/testapp_middlemodel",
            "$ref in items moet '#/$defs/testapp_middlemodel' zijn in JSON Schema voor n-to-m FK",
        )

    def test_guid(self):
        """UUIDField moet type 'string' en format 'uuid' hebben in JSON Schema."""

        field = _bare_field(base_models.UUIDField)
        field.config = Config()
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["type"], "string", "type moet 'string' zijn in JSON Schema voor UUIDField")
        self.assertEqual(prop["format"], "uuid", "format moet 'uuid' zijn in JSON Schema voor UUIDField")

    def test_geometry(self):
        """GeometryField moet type 'object' en format 'geometry' hebben in JSON Schema."""

        field = _bare_field(base_models.GeometryField)
        field.config = Config()
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["type"], "object", "type moet 'object' zijn in JSON Schema voor GeometryField")

    def test_integer_with_precision(self):
        """IntegerField met precision moet type 'integer' en het juiste precision attribuut hebben in JSON Schema."""

        field = _bare_field(dj_models.IntegerField)
        field.config = Config(precision=5)
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["type"], "integer", "type moet 'integer' zijn in JSON Schema voor IntegerField")
        self.assertEqual(
            prop["precision"], 5, "precision moet 5 zijn in JSON Schema voor IntegerField met precision=5"
        )

    def test_float_with_precision(self):
        """FloatField met precision moet type 'number' en het juiste precision attribuut hebben in JSON Schema."""

        field = _bare_field(dj_models.FloatField)
        field.config = Config(precision=3)
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["type"], "number", "type moet 'number' zijn in JSON Schema voor FloatField")
        self.assertEqual(prop["precision"], 3, "precision moet 3 zijn in JSON Schema voor FloatField met precision=3")

    def test_date(self):
        """DateField moet type 'string' en format 'date' hebben in JSON Schema."""

        field = _bare_field(dj_models.DateField)
        field.config = Config()
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["type"], "string", "type moet 'string' zijn in JSON Schema voor DateField")
        self.assertEqual(prop["format"], "date", "format moet 'date' zijn in JSON Schema voor DateField")

    def test_datetime(self):
        """DateTimeField moet type 'string' en format 'date-time' hebben in JSON Schema."""

        field = _bare_field(dj_models.DateTimeField)
        field.config = Config()
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["type"], "string", "type moet 'string' zijn in JSON Schema voor DateTimeField")
        self.assertEqual(prop["format"], "date-time", "format moet 'date-time' zijn in JSON Schema voor DateTimeField")

    def test_time(self):
        """TimeField moet type 'string' en format 'time' hebben in JSON Schema."""

        field = _bare_field(dj_models.TimeField)
        field.config = Config()
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["type"], "string", "type moet 'string' zijn in JSON Schema voor TimeField")
        self.assertEqual(prop["format"], "time", "format moet 'time' zijn in JSON Schema voor TimeField")

    def test_boolean(self):
        """BooleanField moet type 'boolean' hebben in JSON Schema."""

        field = _bare_field(dj_models.BooleanField)
        field.config = Config()
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(prop["type"], "boolean", "type moet 'boolean' zijn in JSON Schema voor BooleanField")

    def test_nullable_boolean(self):
        """NullBooleanField moet type ['boolean', 'null'] hebben in JSON Schema."""

        field = _bare_field(dj_models.NullBooleanField)
        field.config = Config()
        prop = self._gen()._field_to_property(field=field)
        self.assertEqual(
            prop["type"],
            ["boolean", "null"],
            "type moet ['boolean', 'null'] zijn in JSON Schema voor NullBooleanField",
        )


class TestModelPropertiesReverseRelations(UnitTestCase):
    """model_properties(): cardinaliteit van reverse relaties.

    Regressie voor een bug waarbij OneToOneRel (Django's reverse kant van een
    OneToOneField) werd opgevangen door de generieke (ManyToOneRel,
    ManyToManyRel)-check — OneToOneRel is daar een subklasse van — en dus altijd
    als `type: array` werd geëxporteerd. Hasura leidt object- vs
    array-relationship zelf af uit de unieke DB-constraint die een
    OneToOneField meebrengt, dus voor zo'n veld verwacht de mutation-input een
    los object (`*_obj_rel_insert_input`) i.p.v. een array
    (`*_arr_rel_insert_input`). Het mismatch-schema liet de frontend
    `{data: [...], on_conflict}` versturen waar Hasura `{data: {...},
    on_conflict}` verwachtte ("expected an object ... but found a list").
    """

    def _gen(self):
        return SchemaGenerator(models=[])

    def test_reverse_one_to_one_emits_ref_object_not_array(self):
        """MiddleModel.extended (reverse OneToOneField vanuit MiddleExtendedModel) moet een los $ref-object zijn."""
        from tests.testapp.models import MiddleModel

        props, _required = self._gen().model_properties(MiddleModel)
        prop = props["extended"]
        self.assertNotEqual(prop.get("type"), "array", "Reverse OneToOneField mag niet als array worden geëxporteerd")
        self.assertNotIn("items", prop, "Reverse OneToOneField mag geen 'items' (array-vorm) hebben")
        self.assertEqual(
            prop.get("$ref"),
            "#/$defs/testapp_middleextendedmodel",
            "Reverse OneToOneField moet een direct $ref naar het doelmodel zijn",
        )

    def test_reverse_foreign_key_still_emits_array(self):
        """ParentModel.middle_models (reverse gewone FK vanuit MiddleModel) moet een array blijven."""
        from tests.testapp.models import ParentModel

        props, _required = self._gen().model_properties(ParentModel)
        prop = props["middle_models"]
        self.assertEqual(prop.get("type"), "array", "Reverse gewone FK moet als array worden geëxporteerd")
        self.assertIn("$ref", prop.get("items", {}), "Array-item moet een $ref naar het doelmodel bevatten")
