from enum import Enum

from rgs_django_utils.forms.fields.Field import Field


class ValueType(Enum):
    STRING = "string"
    INTEGER = "integer"


class SelectOptionsConfig:
    def __init__(self, label_field: str = "label", value_field: str = "value", url: str = None, params: dict = None):
        self.label_field = label_field
        self.value_field = value_field
        self.url = url
        self.params = params

    def __dict__(self):
        out = {"label_field": self.label_field, "value_field": self.value_field}
        if self.url is not None:
            out["url"] = self.url
        if self.params is not None:
            out["params"] = self.params
        return out


class SelectField(Field):
    def __init__(
        self,
        value=None,
        value_type: ValueType = ValueType.STRING,
        options: list = None,
        options_config: SelectOptionsConfig = None,
        **kwargs,
    ):
        super().__init__(value=value, **kwargs)
        self.field_type = "SelectInput"
        self.value_type = value_type
        self.instance_type = str if value_type == ValueType.STRING else int
        self.options = options
        self.options_config = options_config

    def to_python(self, value):
        return str(value)

    def to_json(self, value):
        return str(value)

    def __dict__(self):
        out = super().__dict__()
        out["valueType"] = self.value_type.value
        out["options"] = self.options
        if self.options_config is not None:
            out["optionsConfig"] = self.options_config.__dict__()
        return out
