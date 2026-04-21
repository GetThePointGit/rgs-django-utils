from rgs_django_utils.forms.fields.Field import Field


class BooleanField(Field):
    """Boolean form field with customisable true / false / null renderings.

    Parameters
    ----------
    value : bool, optional
        Initial value.
    **kwargs
        Forwarded to :class:`~rgs_django_utils.forms.fields.Field.Field`.
        Recognised extras: ``true_value`` (default ``True``),
        ``false_value`` (default ``False``), ``null_value`` (default
        ``None``) — used when serialising to payloads where the wire
        format uses strings / numbers instead of Python booleans.
    """

    def __init__(self, value: bool = None, **kwargs):
        super().__init__(**kwargs)
        self.field_type = "BooleanInput"
        self.instance_type = bool

        self.true_value = kwargs.get("true_value", True)
        self.false_value = kwargs.get("false_value", False)
        self.null_value = kwargs.get("null_value", None)

        # transform the value to a boolean
