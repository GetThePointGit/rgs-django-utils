"""Tests for rgs_django_utils.commands.export_datamodel_to_json_schema.

Covers the metadata-emission additions (unit, precision, docFull, modules)
and the modules-normalisation helper. Geen Django DB nodig — alle tests
werken op losse veld-instanties met handmatig geprikte Config.
"""

import pytest
from django.db import models as dj_models

from rgs_django_utils.commands.export_datamodel_to_json_schema import (
    SchemaGenerator,
    _modules_to_list,
)
from rgs_django_utils.database.dj_extended_models import Config


class TestModulesToList:
    """Pure-function test for the modules normalisation helper."""

    def test_none_returns_none(self):
        assert _modules_to_list(None) is None

    def test_wildcard_returns_none(self):
        assert _modules_to_list("*") is None

    def test_string_returns_singleton_list(self):
        assert _modules_to_list("mod_a") == ["mod_a"]

    def test_list_of_strings_passthrough(self):
        assert _modules_to_list(["mod_a", "mod_b"]) == ["mod_a", "mod_b"]

    def test_tuple_of_strings_returns_list(self):
        assert _modules_to_list(("a", "b")) == ["a", "b"]

    def test_empty_iterable_returns_none(self):
        assert _modules_to_list([]) is None

    def test_non_iterable_returns_none(self):
        assert _modules_to_list(123) is None

    def test_non_string_items_stringified(self):
        class _M:
            def __str__(self):
                return "module_x"

        assert _modules_to_list([_M(), _M()]) == ["module_x", "module_x"]


def _bare_field(field_cls, name: str = "depth", **kwargs):
    """Construct a Django field with the minimum attributes used by the exporter.

    The exporter only reads introspection attributes; we side-step
    contribute_to_class so we do not need a registered model.
    """
    field = field_cls(**kwargs)
    field.name = name
    field.column = name
    return field


class TestFieldToPropertyMetadata:
    """Verify that the new Config metadata reaches the JSON Schema property."""

    def _gen(self):
        return SchemaGenerator(models=[])

    def test_unit_emitted_from_doc_unit(self):
        field = _bare_field(dj_models.FloatField)
        field.config = Config(doc_unit="m")
        prop = self._gen()._field_to_property(field=field)
        assert prop["unit"] == "m"

    def test_precision_emitted(self):
        field = _bare_field(dj_models.FloatField)
        field.config = Config(precision=2)
        prop = self._gen()._field_to_property(field=field)
        assert prop["precision"] == 2

    def test_doc_full_emitted_as_docFull(self):
        field = _bare_field(dj_models.FloatField)
        field.config = Config(doc_full="Uitgebreide uitleg over diepte.")
        prop = self._gen()._field_to_property(field=field)
        assert prop["docFull"] == "Uitgebreide uitleg over diepte."

    def test_modules_list_emitted(self):
        field = _bare_field(dj_models.IntegerField)
        field.config = Config(modules=["mod_a", "mod_b"])
        prop = self._gen()._field_to_property(field=field)
        assert prop["modules"] == ["mod_a", "mod_b"]

    def test_modules_wildcard_not_emitted(self):
        field = _bare_field(dj_models.IntegerField)
        field.config = Config(modules="*")
        prop = self._gen()._field_to_property(field=field)
        assert "modules" not in prop

    def test_no_metadata_keeps_property_clean(self):
        field = _bare_field(dj_models.FloatField)
        prop = self._gen()._field_to_property(field=field)
        for key in ("unit", "precision", "docFull", "modules"):
            assert key not in prop

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
        assert prop["description"] == "diepte"
        assert prop["unit"] == "m"
        assert prop["precision"] == 2
        assert prop["docFull"] == "lange uitleg"

    def test_precision_zero_emitted(self):
        """precision=0 is een geldige waarde en moet meekomen."""
        field = _bare_field(dj_models.IntegerField)
        field.config = Config(precision=0)
        prop = self._gen()._field_to_property(field=field)
        assert prop["precision"] == 0
