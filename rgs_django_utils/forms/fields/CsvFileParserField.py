from typing import Optional

from rgs_django_utils.forms.fields.Field import Field
from rgs_django_utils.forms.file_mixin import FileHeaderMixin


def get_separator_from_file(proj_file: FileHeaderMixin) -> Optional[str]:
    """Return the separator used in the project file, or None if not found."""
    first_100_bytes: Optional[bytes] = proj_file.first_100_bytes() if proj_file else None
    first_lines = first_100_bytes.decode("utf-8", errors="ignore").splitlines() if first_100_bytes else []
    if len(first_lines) == 0:
        return None
    first_line = first_lines[0]
    if ";" in first_line:
        return ";"
    elif "\t" in first_line:
        return "\t"
    elif " " in first_line:
        return " "
    elif "," in first_line:
        return ","
    return None


def get_decimal_separator_from_file(proj_file: FileHeaderMixin, separator: str, has_header: bool) -> Optional[str]:
    """Return the decimal separator used in the project file, or None if not found."""
    first_100_bytes: Optional[bytes] = proj_file.first_100_bytes() if proj_file else None
    first_lines = first_100_bytes.decode("utf-8", errors="ignore").splitlines() if first_100_bytes else []
    if len(first_lines) == 0 or (len(first_lines) == 1 and has_header):
        return None
    first_line = first_lines[1] if has_header and len(first_lines) > 1 else first_lines[0]
    values = first_line.split(separator)
    for value in values:
        if '"' in value:
            continue  # Skip quoted values
        if "." in value and "," in value:
            continue  # Ambiguous, skip this value
        elif "." in value:
            return "."
        elif "," in value:
            return ","
    return None


class CsvFileParserField(Field):
    """CSV file parser form field.

    Parameters
    ----------
    value : dict, optional
        Initial value.
    **kwargs
        Forwarded to :class:`~rgs_django_utils.forms.fields.Field.Field`.
        Recognised extras: ``has_header``, ``separator``, ``decimal_separator`` — used when serialising to payloads where the wire format uses strings / numbers or booleans instead of dicts.
    """

    @classmethod
    def create_from_file(cls, proj_file: FileHeaderMixin, has_header=False, **kwargs) -> "CsvFileParserField":
        """Create a CsvFileParserField with values derived from a project file.

        Parameters
        ----------
        proj_file : FileHeaderMixin
            The project file to derive values from.
        has_header : bool, optional
            Whether the CSV file has a header row. Default is False.
        **kwargs
            Forwarded to :class:`~rgs_django_utils.forms.fields.Field.Field`.
            Recognised extras: ``has_header``, ``separator``, ``decimal_separator`` — used when serialising to payloads where the wire format uses strings / numbers or booleans instead of dicts.
        """
        internal_dict = {
            "has_header": has_header,
            "separator": get_separator_from_file(proj_file) if proj_file else None,
            "decimal_separator": (
                get_decimal_separator_from_file(
                    proj_file, get_separator_from_file(proj_file) if proj_file else None, has_header=has_header
                )
                if proj_file
                else None
            ),
        }
        return cls(
            has_header=has_header,
            value=internal_dict,
            **kwargs,
        )

    def __init__(self, **kwargs):
        # has_header/separator/decimal_separator are convenience extras for
        # building `value`, not Field.__init__ parameters (it has no **kwargs
        # catch-all) — pop them so they aren't forwarded to super().__init__.
        has_header = kwargs.pop("has_header", False)
        separator = kwargs.pop("separator", None)
        decimal_separator = kwargs.pop("decimal_separator", None)

        value = kwargs.get("value", None)
        if value is None:
            value = {
                "has_header": has_header,
                "separator": separator,
                "decimal_separator": decimal_separator,
            }
            kwargs["value"] = value
        else:
            if "has_header" not in value:
                value["has_header"] = has_header
            if "separator" not in value:
                value["separator"] = separator
            if "decimal_separator" not in value:
                value["decimal_separator"] = decimal_separator

        super().__init__(**kwargs)
        self.field_type = "CsvFileParserInput"
        self.instance_type = dict

    @property
    def separator(self) -> str | None:
        """Return the separator used in the CSV file."""
        return self._value.get("separator")

    @property
    def decimal_separator(self) -> str | None:
        """Return the decimal separator used in the CSV file."""
        return self._value.get("decimal_separator")

    @property
    def has_header(self) -> bool:
        """Return True if the CSV file has a header, False otherwise."""
        return self._value.get("has_header") or False

    def sanitize(self) -> bool:
        """Check required-ness and Python type; record errors if they fail.

        Returns
        -------
        bool
            ``True`` when sanitisation succeeded and validation should
            continue; ``False`` on a hard failure.
        """
        if not super().sanitize():
            return False

        if self.required:
            separator = self.value.get("separator") if self.value else None
            if separator is None:
                self.errors.append({"type": "required", "message": "separator is required"})
                return False
            elif not isinstance(separator, str) or len(separator) != 1:
                self.errors.append({"type": "invalid", "message": "separator must be a single character string"})
                return False

            decimal_separator = self.value.get("decimal_separator") if self.value else None
            if decimal_separator is None:
                self.errors.append({"type": "required", "message": "decimal_separator is required"})
                return False
            elif not isinstance(decimal_separator, str) or len(decimal_separator) != 1:
                self.errors.append(
                    {"type": "invalid", "message": "decimal_separator must be a single character string"}
                )
                return False

            has_header = self.value.get("has_header") if self.value else None
            if has_header is None:
                self.errors.append({"type": "required", "message": "has_header is required"})
                return False
            elif not isinstance(has_header, bool):
                self.errors.append({"type": "invalid", "message": "has_header must be a boolean"})
                return False
        return True
