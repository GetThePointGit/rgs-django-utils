"""Tests voor DynamicStorageFieldFile/DynamicStorageFileField.

Dekt de storage-resolutie per rij (via storage_key_attname op de instance),
de fallback naar "default", de no-op storage-setter (die Django's
onvoorwaardelijke `self.storage = field.storage` in FieldFile.__init__ moet
opvangen zonder de dynamische resolutie te overschrijven), de TypeError-guard
tegen een vaste storage=-kwarg, en deconstruct() voor migraties.

Geen Django DB nodig — FieldFile wordt direct geïnstantieerd met een
stub-instance, en STORAGES wijst naar InMemoryStorage.
"""

from django.core.files.storage import InMemoryStorage, storages
from django.test import SimpleTestCase, override_settings

from rgs_django_utils.database.dj_extended_models import (
    DynamicStorageFieldFile,
    DynamicStorageFileField,
)

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "alt": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
}


class _Instance:
    """Stub model-instance met losse attributen voor de storage-sleutel."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


@override_settings(STORAGES=TEST_STORAGES)
class TestDynamicStorageFieldFile(SimpleTestCase):
    def _make_field(self, storage_key_attname="storage_key"):
        return DynamicStorageFileField(storage_key_attname=storage_key_attname)

    def test_resolves_storage_from_instance_attribute(self):
        field = self._make_field()
        instance = _Instance(storage_key="alt")
        field_file = DynamicStorageFieldFile(instance, field, "some/path.txt")
        self.assertIs(field_file.storage, storages["alt"])

    def test_falls_back_to_default_when_attribute_missing(self):
        field = self._make_field()
        instance = _Instance()
        field_file = DynamicStorageFieldFile(instance, field, "some/path.txt")
        self.assertIs(field_file.storage, storages["default"])

    def test_falls_back_to_default_when_attribute_is_falsy(self):
        field = self._make_field()
        instance = _Instance(storage_key="")
        field_file = DynamicStorageFieldFile(instance, field, "some/path.txt")
        self.assertIs(field_file.storage, storages["default"])

    def test_respects_custom_storage_key_attname(self):
        field = self._make_field(storage_key_attname="klant_storage")
        instance = _Instance(klant_storage="alt")
        field_file = DynamicStorageFieldFile(instance, field, "some/path.txt")
        self.assertIs(field_file.storage, storages["alt"])

    def test_storage_setter_is_noop(self):
        field = self._make_field()
        instance = _Instance(storage_key="alt")
        field_file = DynamicStorageFieldFile(instance, field, "some/path.txt")
        field_file.storage = storages["default"]
        self.assertIs(field_file.storage, storages["alt"])


class TestDynamicStorageFileField(SimpleTestCase):
    def test_default_storage_key_attname(self):
        field = DynamicStorageFileField()
        self.assertEqual(field.storage_key_attname, "storage_key")

    def test_custom_storage_key_attname(self):
        field = DynamicStorageFileField(storage_key_attname="klant_storage")
        self.assertEqual(field.storage_key_attname, "klant_storage")

    def test_fixed_storage_kwarg_raises_typeerror(self):
        with self.assertRaises(TypeError):
            DynamicStorageFileField(storage=InMemoryStorage())

    def test_attr_class_is_dynamic_storage_field_file(self):
        self.assertIs(DynamicStorageFileField.attr_class, DynamicStorageFieldFile)

    def test_deconstruct_includes_storage_key_attname(self):
        field = DynamicStorageFileField(storage_key_attname="klant_storage")
        _, _, _, kwargs = field.deconstruct()
        self.assertEqual(kwargs["storage_key_attname"], "klant_storage")

    def test_deconstruct_roundtrip_reconstructs_equivalent_field(self):
        field = DynamicStorageFileField(storage_key_attname="klant_storage")
        _, _, args, kwargs = field.deconstruct()
        reconstructed = DynamicStorageFileField(*args, **kwargs)
        self.assertEqual(reconstructed.storage_key_attname, "klant_storage")
