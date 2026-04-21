from typing import TypedDict


class ValidationErrorMessage(TypedDict):
    message: str
    type: str


class Field:
    """Base class for every form field in this package.

    Stores the value plus the documentation metadata and runs validation
    on demand. Subclasses (``StringField``, ``IntegerField``, …) set
    ``field_type`` / ``instance_type`` and override :meth:`validation_extra`
    with type-specific checks. Validation is layered:

    1. :meth:`sanitize` enforces required-ness and the Python-type
       match against ``instance_type``.
    2. :meth:`validation_extra` adds type-specific rules (range, length).
    3. Each callable in ``validators`` is called with the field itself
       and can append further errors.

    Parameters
    ----------
    name : str
        Machine-readable field name (matches the column/key).
    label : str
        Human-readable label shown in the UI.
    value : Any, optional
        Initial value. Empty string is coerced to ``None``.
    default_value : Any, optional
        Value used when the field is absent from the payload.
    required : bool, optional
        Default ``True``. ``None`` is invalid when required.
    unit : str, optional
        Unit suffix shown next to the input.
    doc_short : str, optional
        Short help text / tooltip.
    doc_full : str, optional
        Long-form help text.
    doc_development : str, optional
        Developer-facing notes (not rendered to end users).
    validators : list of callable, optional
        Extra validators ``(field) -> bool`` — return ``False`` to halt
        the chain, append ``ValidationErrorMessage`` entries via
        ``field._errors``.

    Raises
    ------
    ValueError
        If *name* or *label* is ``None``.
    """

    def __init__(
        self,
        name: str,  # column_name
        label: str,
        value=None,
        default_value=None,
        required=True,
        unit=None,  # doc_unit
        doc_short=None,
        doc_full=None,
        doc_development=None,
        validators=None,
    ):
        # raise when name or verbose_name is None
        for var in [name, label]:
            if var is None:
                raise ValueError(f"{var} cannot be None")

        self.field_type = "field"
        self.instance_type = None

        self.name = name
        self.label = label
        self.required = required
        self.unit = unit
        self.default_value = default_value

        self.doc_short = doc_short
        self.doc_full = doc_full
        self.doc_development = doc_development

        self.validators = validators or []

        # for processing, also include value
        self._value = value
        self._errors: None | list[ValidationErrorMessage] = None

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if value == "":
            value = None
        self._value = value
        self._errors = None

    @property
    def errors(self):
        if self._errors is None:
            self.validate()
        return self._errors

    @property
    def is_valid(self):
        return len(self.errors) == 0

    def sanitize(self) -> bool:
        """Check required-ness and Python type; record errors if they fail.

        Returns
        -------
        bool
            ``True`` when sanitisation succeeded and validation should
            continue; ``False`` on a hard failure.
        """
        if self.required and self.value is None:
            self.errors.append({"type": "required", "message": "value is required"})
            return False
        if (
            self.instance_type is not None
            and self.value is not None
            and not isinstance(self.value, self.instance_type)
        ):
            self.errors.append(
                {
                    "type": "value-type",
                    "message": f"Value must be a {self.instance_type}, got {type(self.value)}: {self.value}",
                }
            )
            return False
        return True

    def validation_extra(self) -> bool:
        """Subclass hook for type-specific validation.

        Override to add range checks, length checks, etc. Returning
        ``False`` halts the chain; returning ``True`` lets the
        ``validators`` list run next. Errors should be appended to
        ``self._errors`` directly.
        """
        return True

    def validate(self) -> bool:
        """Run the full validation chain and cache the errors.

        Returns
        -------
        bool
            ``True`` when the field is valid. Side effect: populates
            ``self._errors``.
        """
        self._errors = []

        if not self.sanitize():
            return False

        if not self.validation_extra():
            return False

        for validator in self.validators:
            if not validator(self):
                return False

        return len(self._errors) == 0

    def __str__(self):
        return f"{self.name}: {self.value}"

    def __dict__(self):
        out = {
            "_type": self.field_type,
            "name": self.name,
            "label": self.label,
            "required": self.required,
            "unit": self.unit,
            "helpText": self.doc_short,  # == help_text
            # "doc_development": self.doc_development,
            "value": self.value,
            "defaultValue": self.default_value,
            # "validators": self.validators,
        }
        # filter out empty values
        return {k: v for k, v in out.items() if v is not None}
