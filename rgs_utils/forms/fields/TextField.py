from rgs_utils.forms.fields.StringField import StringField


class TextField(StringField):
    def __init__(self, value: str = None, **kwargs):
        super().__init__(value=value, **kwargs)
        self.field_type = "TextInput"
