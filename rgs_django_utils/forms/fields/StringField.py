from rgs_django_utils.forms.fields.Field import Field


class StringField(Field):
    def __init__(self, value: str = None, max_length=None, **kwargs):
        super().__init__(value=value, **kwargs)
        self.field_type = "StringInput"
        self.instance_type = str
        self.max_length = max_length

    def extra_validate(self):
        if self.max_length is not None:
            if len(self.value) > self.max_length:
                self.errors.append(
                    {"type": "max-length", "message": f"Value exceeds max length of {self.max_length}: {self.value}"}
                )
                return True  # continue validation

    def to_python(self, value):
        return str(value)

    def to_json(self, value):
        return str(value)

    def __dict__(self):
        out = super().__dict__()
        if self.max_length is not None:
            out["max_length"] = self.max_length
        return out
