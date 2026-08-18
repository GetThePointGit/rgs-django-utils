import typing


class FileHeaderMixin:
    """A mixin for file-like objects that provides a method to read the first 100 bytes.

    Assumes that the class using this mixin has a `file` attribute that supports the `open` method.
    """

    def first_100_bytes(self) -> typing.Optional[bytes]:
        """Return the first 100 bytes of the file, or None if the file is not available."""
        if self.file:
            with self.file.open("rb") as f:
                return f.read(100)
        return None

    def is_png(self) -> bool:
        """Check if the file is a PNG image based on its signature."""
        first_8_bytes = self.first_100_bytes()[:8]
        return first_8_bytes == b"\x89PNG\r\n\x1a\n"

    def is_jpeg(self) -> bool:
        """Check if the file is a JPEG image based on its signature."""
        first_4_bytes = self.first_100_bytes()[:4]
        return (
            first_4_bytes == (b"\xff\xd8\xff\xdb")
            or first_4_bytes == (b"\xff\xd8\xff\xe0")
            or first_4_bytes == (b"\xff\xd8\xff\xee")
            or first_4_bytes == (b"\xff\xd8\xff\xe1")
        )

    def is_tiff(self) -> bool:
        """Check if the file is a TIFF image based on its signature."""
        first_4_bytes = self.first_100_bytes()[:4]
        return first_4_bytes in (b"II*\x00", b"MM\x00*")

    def is_pdf(self) -> bool:
        """Check if the file is a PDF based on its signature."""
        first_4_bytes = self.first_100_bytes()[:4]
        return first_4_bytes == b"%PDF"

    def is_dxf(self) -> bool:
        """Check if the file is a DXF based on its signature."""
        first_6_bytes = self.first_100_bytes()[:6]
        return (
            first_6_bytes == b"AC1006"
            or first_6_bytes == b"AC1012"
            or first_6_bytes == b"AC1014"
            or first_6_bytes == b"AC1015"
            or first_6_bytes == b"AC1018"
        )

    def is_zip(self) -> bool:
        """Check if the file is a ZIP based on its signature."""
        first_4_bytes = self.first_100_bytes()[:4]
        return first_4_bytes in [
            b"PK\x03\x04",  # default archive
            b"PK\x05\x06",  # empty archive
            b"PK\x07\x08",  # spanned archive
        ]

    def is_msaccess(self) -> bool:
        """Check if the file is a Microsoft Access database based on its signature."""
        first_20_bytes = self.first_100_bytes()[:20]
        return first_20_bytes in [
            b"\x00\x01\x00\x00\x53\x74\x61\x6e\x64\x61\x72\x64\x20\x4a\x65\x74\x20\x44\x42",  # Standard Jet DB
            b"\x00\x01\x00\x00\x53\x74\x61\x6e\x64\x61\x72\x64\x20\x41\x43\x45\x20\x44\x42",  # Standard ACE DB
        ]

    def is_shp(self) -> bool:
        """Check if the file is a Shapefile based on its signature."""
        first_4_bytes = self.first_100_bytes()[:4]
        return first_4_bytes == b"\x00\x00\x27\x0a"

    def is_shx(self) -> bool:
        """Check if the file is a Shapefile index based on its signature."""
        first_4_bytes = self.first_100_bytes()[:4]
        return first_4_bytes == b"\x00\x00\x27\x0a"

    def is_dbf3(self) -> bool:
        """Check if the file is a dBASE database based on its signature."""
        first_1_byte = self.first_100_bytes()[:1]
        return first_1_byte in [b"\x03"]

    def is_geopackage(self) -> bool:
        """Check if the file is a GeoPackage based on its signature."""
        first_16_bytes = self.first_100_bytes()[:16]
        return first_16_bytes == b"SQLite format 3\x00"
