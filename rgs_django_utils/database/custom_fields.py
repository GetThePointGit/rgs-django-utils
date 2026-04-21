from django.db.models import Field, TextField
from django.utils.translation import gettext_lazy as _


class TextStringField(TextField):
    """``TextField`` that renders with a single-line string widget in forms.

    Storage is identical to :class:`~django.db.models.TextField`, but the
    generated form field uses the default (single-line) widget instead of
    a ``Textarea``. Use this when the value is free-form text that happens
    to be stored as ``TEXT`` in Postgres (because of length or indexing
    reasons) but should be edited on one line.

    Examples
    --------
    >>> class User(models.Model):
    ...     fullname = TextStringField(blank=True)   # doctest: +SKIP
    """

    description = _("Text (with string widget)")

    def formfield(self, **kwargs):
        """Return a ``CharField`` form field, forcing the default widget.

        Overriding ``widget`` to ``None`` makes Django fall back to
        ``TextInput`` instead of ``Textarea``.
        """
        # Passing max_length to forms.CharField means that the value's length
        # will be validated twice. This is considered acceptable since we want
        # the value in the form field (to pass into widget for example).
        return Field.formfield(self, **{"max_length": self.max_length, **kwargs, "widget": None})
