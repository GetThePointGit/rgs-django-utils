from unittest import TestCase

from rgs_django_utils.forms.fields.CsvFileParserField import (
    get_decimal_separator_from_file,
    get_separator_from_file,
)
from rgs_django_utils.forms.file_mixin import FileHeaderMixin


class TestCsvFileParserField(TestCase):
    class ProjectFile(FileHeaderMixin):
        """A simple subclass of FileHeaderMixin to represent a project file."""

        def __init__(self, content: bytes):
            self.content = content

        def first_100_bytes(self) -> bytes:
            return self.content[:100]

    def _make_project_file(self, content: bytes) -> ProjectFile:
        return self.ProjectFile(content)

    def test_get_separator_from_file(self):
        # Test with a file that has a comma separator
        proj_file_with_comma = self._make_project_file(b"X,Y,Z\n0.1,0.2,0.3\n")
        separator = get_separator_from_file(proj_file_with_comma)
        self.assertEqual(separator, ",")

        # Test with a file that has a semicolon separator
        proj_file_with_semicolon = self._make_project_file(b"X;Y;Z\n0.1;0.2;0.3\n")
        separator = get_separator_from_file(proj_file_with_semicolon)
        self.assertEqual(separator, ";")

        # Test with a file that has a tab separator
        proj_file_with_tab = self._make_project_file(b"X\tY\tZ\n0.1\t0.2\t0.3\n")
        separator = get_separator_from_file(proj_file_with_tab)
        self.assertEqual(separator, "\t")

        # Test with a file that has a space separator
        proj_file_with_space = self._make_project_file(b"X Y Z\n0.1 0.2 0.3\n")
        separator = get_separator_from_file(proj_file_with_space)
        self.assertEqual(separator, " ")

        # Test with a file that has a semicolon separator and a decimal comma
        proj_file_with_semicolon_and_decimal = self._make_project_file(b"0,1;0,2;0,3\n0,1;0,2;0,3\n")
        separator = get_separator_from_file(proj_file_with_semicolon_and_decimal)
        self.assertEqual(separator, ";")

        # Test with a file that has a comma separator and a decimal point
        proj_file_with_comma_and_decimal = self._make_project_file(b"0.1,0.2,0.3\n0.4,0.5,0.6\n")
        separator = get_separator_from_file(proj_file_with_comma_and_decimal)
        self.assertEqual(separator, ",")

        # Test with an empty file
        empty_proj_file = self._make_project_file(b"")
        separator = get_separator_from_file(empty_proj_file)
        self.assertIsNone(separator)

    def test_get_decimal_separator_from_file(self):
        # Test with a file that has a decimal comma
        proj_file_with_decimal_comma = self._make_project_file(b"0,1;0,2;0,3\n0,4;0,5;0,6\n")
        decimal_separator = get_decimal_separator_from_file(proj_file_with_decimal_comma, ";", has_header=False)
        self.assertEqual(decimal_separator, ",")

        # Test with a file that has a decimal point
        proj_file_with_decimal_point = self._make_project_file(b"0.1,0.2,0.3\n0.4,0.5,0.6\n")
        decimal_separator = get_decimal_separator_from_file(proj_file_with_decimal_point, ",", has_header=False)
        self.assertEqual(decimal_separator, ".")

        # Test with a file that has a decimal comma and a header
        proj_file_with_header_and_decimal_comma = self._make_project_file(b"X;Y;Z\n0,1;0,2;0,3\n0,4;0,5;0,6\n")
        decimal_separator = get_decimal_separator_from_file(
            proj_file_with_header_and_decimal_comma, ";", has_header=True
        )
        self.assertEqual(decimal_separator, ",")

        # Test a file with text in the first column and a decimal comma in the second column
        proj_file_with_text_and_decimal_comma = self._make_project_file(b"X;Y;Z\nA;0,2;0,3\nB;0,5;0,6\n")
        decimal_separator = get_decimal_separator_from_file(
            proj_file_with_text_and_decimal_comma, ";", has_header=True
        )
        self.assertEqual(decimal_separator, ",")

        # Test a file with only text
        # Note: Values with a quote are considered text, so the decimal separator cannot be determined
        proj_file_with_text_and_decimal_comma = self._make_project_file(
            b'X,Y,Z\n"0,1","0,2","0,3"\n"0.4","0,5","0,6"\n'
        )
        decimal_separator = get_decimal_separator_from_file(
            proj_file_with_text_and_decimal_comma, ",", has_header=True
        )
        self.assertIsNone(decimal_separator)
