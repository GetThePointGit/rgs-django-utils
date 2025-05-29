from rgs_django_utils.forms.fields.Field import Field


class BooleanField(Field):
    def __init__(self, value: bool = None, **kwargs):
        super().__init__(**kwargs)
        self.field_type = "BooleanInput"
        self.instance_type = bool

        self.true_value = kwargs.get("true_value", True)
        self.false_value = kwargs.get("false_value", False)
        self.null_value = kwargs.get("null_value", None)

        # transform the value to a boolean
