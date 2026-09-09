from unittest import TestCase

from rgs_django_utils.forms.fields.OrderedListField import OrderedListField

AVAILABLE_FIELDS = [
    {"key": "ids", "label": "Id"},
    {"key": "x", "label": "X"},
    {"key": "y", "label": "Y"},
]


class TestOrderedListField(TestCase):
    def _field(self, **kwargs):
        return OrderedListField(
            name="field_order",
            label="Veldvolgorde",
            available_fields=AVAILABLE_FIELDS,
            **kwargs,
        )

    def test_default_value_is_available_fields_in_order(self):
        field = self._field()
        self.assertEqual(
            field.value,
            [{"type": "field", "key": "ids"}, {"type": "field", "key": "x"}, {"type": "field", "key": "y"}],
        )
        self.assertTrue(field.is_valid)

    def test_reordering_is_valid(self):
        field = self._field(
            value=[{"type": "field", "key": "y"}, {"type": "field", "key": "x"}, {"type": "field", "key": "ids"}]
        )
        self.assertTrue(field.is_valid)

    def test_literal_slots_may_be_inserted_freely(self):
        field = self._field(
            value=[
                {"type": "field", "key": "ids"},
                {"type": "literal", "value": ""},
                {"type": "literal", "value": "NAP"},
                {"type": "field", "key": "x"},
                {"type": "field", "key": "y"},
                {"type": "literal", "value": ""},
            ]
        )
        self.assertTrue(field.is_valid)

    def test_missing_field_is_invalid(self):
        field = self._field(value=[{"type": "field", "key": "ids"}, {"type": "field", "key": "x"}])
        self.assertFalse(field.is_valid)
        self.assertEqual(field.errors[0]["type"], "invalid")

    def test_duplicate_field_is_invalid(self):
        field = self._field(
            value=[
                {"type": "field", "key": "ids"},
                {"type": "field", "key": "ids"},
                {"type": "field", "key": "x"},
                {"type": "field", "key": "y"},
            ]
        )
        self.assertFalse(field.is_valid)

    def test_unknown_field_key_is_invalid(self):
        field = self._field(
            value=[
                {"type": "field", "key": "unknown"},
                {"type": "field", "key": "x"},
                {"type": "field", "key": "y"},
            ]
        )
        self.assertFalse(field.is_valid)

    def test_unknown_slot_type_is_invalid(self):
        field = self._field(
            value=[
                {"type": "bogus"},
                {"type": "field", "key": "ids"},
                {"type": "field", "key": "x"},
                {"type": "field", "key": "y"},
            ]
        )
        self.assertFalse(field.is_valid)

    def test_dict_serialization_includes_available_fields(self):
        field = self._field()
        serialized = field.__dict__()
        self.assertEqual(serialized["_type"], "OrderedListInput")
        self.assertEqual(serialized["availableFields"], AVAILABLE_FIELDS)
