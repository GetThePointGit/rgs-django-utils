from rgs_utils.forms.fields.Field import Field


class FloatField(Field):
    def __init__(self, value: float = None, precision: int = 3, **kwargs):
        super().__init__(value=value, **kwargs)
        self.field_type = "FloatInput"
        self.instance_type = float

        self.precision = precision

    def to_python(self, value):
        return float(value)

    def to_json(self, value):
        return float(value)

    def __dict__(self):
        out = super().__dict__()
        out["precision"] = self.precision
        return out
