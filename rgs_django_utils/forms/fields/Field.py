from typing import TypedDict


class ValidationErrorMessage(TypedDict):
    message: str
    type: str


class Field:
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
        """Sanitize the field value. For extra sanitization, override sanitize_extra or add sanitizers."""
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
        """Extra validation for the field type, to be implemented in subclasses.

        :return: if the validation is successful or if validation could continue (to catch multiple errors at once)
        """
        return True

    def validate(self) -> bool:
        """Validate the field value. For extra validation, override validation_extra or add validators."""
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
