from rgs_django_utils.forms.fields.Field import Field


class OrderedListField(Field):
    """Reorderable list of fixed fields plus freely-editable literal slots.

    Represents an ordering problem where a fixed set of named fields must
    each appear exactly once (their position is user-configurable, their
    identity is not), interspersed with any number of free-text "literal"
    slots the user can add, remove, reorder, and fill in independently. A
    literal slot with an empty string represents a required-but-blank
    column; a literal slot with text represents a fixed constant value at
    that position (e.g. a datum tag or a format-version flag).

    Parameters
    ----------
    available_fields : list of dict
        The fixed fields for this list, each ``{"key": str, "label": str}``.
        Every key must appear exactly once in ``value``, in some order.
    value : list of dict, optional
        Ordered list of slots. Each slot is either ``{"type": "field",
        "key": <one of available_fields' keys>}`` or ``{"type": "literal",
        "value": <str>}``. Defaults to ``available_fields`` in their given
        order (one field-slot per field, no literal slots).
    **kwargs
        Forwarded to :class:`~rgs_django_utils.forms.fields.Field.Field`.
    """

    def __init__(self, available_fields: list[dict], value: list[dict] = None, **kwargs):
        self.available_fields = available_fields
        if value is None:
            value = [{"type": "field", "key": f["key"]} for f in available_fields]
        super().__init__(value=value, **kwargs)
        self.field_type = "OrderedListInput"
        self.instance_type = list

    def validation_extra(self) -> bool:
        """Check that every available field appears exactly once and slots are well-formed."""
        known_keys = {f["key"] for f in self.available_fields}
        seen_keys = set()

        for slot in self.value:
            if not isinstance(slot, dict) or "type" not in slot:
                self.errors.append({"type": "invalid", "message": f"Invalid slot: {slot}"})
                return False

            if slot["type"] == "field":
                key = slot.get("key")
                if key not in known_keys:
                    self.errors.append({"type": "invalid", "message": f"Unknown field key: {key}"})
                    return False
                if key in seen_keys:
                    self.errors.append({"type": "invalid", "message": f"Field key appears more than once: {key}"})
                    return False
                seen_keys.add(key)
            elif slot["type"] == "literal":
                if not isinstance(slot.get("value", ""), str):
                    self.errors.append({"type": "invalid", "message": f"Literal slot value must be a string: {slot}"})
                    return False
            else:
                self.errors.append({"type": "invalid", "message": f"Unknown slot type: {slot['type']}"})
                return False

        missing = known_keys - seen_keys
        if missing:
            self.errors.append({"type": "invalid", "message": f"Missing required field(s): {sorted(missing)}"})
            return False

        return True

    def __dict__(self):
        out = super().__dict__()
        out["availableFields"] = self.available_fields
        return out
