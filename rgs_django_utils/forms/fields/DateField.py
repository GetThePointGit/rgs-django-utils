from datetime import date

from rgs_django_utils.forms.fields.Field import Field


class DateField(Field):
    """Date form field; value is an ISO-8601 date string (``YYYY-MM-DD``).

    Parameters
    ----------
    value : str, optional
        Initial value as an ISO-8601 date string.
    """

    def __init__(self, value: str = None, **kwargs):
        super().__init__(value=value, **kwargs)
        self.field_type = "DateInput"
        self.instance_type = str

    def validation_extra(self) -> bool:
        if self.value is not None:
            try:
                date.fromisoformat(self.value)
            except ValueError:
                self.errors.append(
                    {
                        "type": "date-format",
                        "message": f"Value must be an ISO-8601 date (YYYY-MM-DD), got: {self.value}",
                    }
                )
                return False
        return True

    def to_python(self, value):
        return date.fromisoformat(value)

    def to_json(self, value):
        return value.isoformat() if isinstance(value, date) else value
