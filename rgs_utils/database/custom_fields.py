from django.db.models import Field
from django.utils.translation import gettext_lazy as _

from rgs_utils.database.dj_extended_models import TextField


class TextStringField(TextField):
    # textfield with string widget

    description = _("Text (with string widget)")

    def formfield(self, **kwargs):
        # Passing max_length to forms.CharField means that the value's length
        # will be validated twice. This is considered acceptable since we want
        # the value in the form field (to pass into widget for example).
        return Field.formfield(self, **{"max_length": self.max_length, **kwargs, "widget": None})
