from rgs_utils.forms.fields.Field import Field


class IntegerField(Field):
    def __init__(self, value: int = None, **kwargs):
        super().__init__(value=value, **kwargs)
        self.field_type = "IntegerInput"
        self.instance_type = int

    def validate(self) -> bool:
        if super().validate():
            if self.value is not None and not isinstance(self.value, int):
                self.errors.append(
                    {"type": "data-type", "message": f"Value must be an integer, got {type(self.value)}: {self.value}"}
                )
                return False
            return True
        return False

    def to_python(self, value):
        return int(value)

    def to_json(self, value):
        return int(value)

    def __dict__(self):
        out = super().__dict__()
        return out
