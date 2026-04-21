from rgs_django_utils.forms.fields.StringField import StringField


class TextField(StringField):
    """Multi-line text form field — same validation as :class:`StringField`, ``Textarea`` widget."""

    def __init__(self, value: str = None, **kwargs):
        super().__init__(value=value, **kwargs)
        self.field_type = "TextInput"
