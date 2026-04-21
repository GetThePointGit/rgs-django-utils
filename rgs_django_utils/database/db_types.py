GENERIC_EXCEL = "generic_xlsx"
GENERIC_OGR = "generic_ogr"


class ImportMethod:
    """Row-level strategies for the upsert helpers in this package.

    Attributes
    ----------
    ONLY_NEW : str
        Insert rows not yet present; existing rows are left untouched.
    ONLY_UPDATE : str
        Update existing rows; rows that don't match are ignored.
    OVERWRITE : str
        Insert missing rows and overwrite existing ones (default upsert).
    REPLACE : str
        Make the target match the input exactly — rows absent from the
        input are deleted.
    """

    ONLY_NEW = "only_new"
    ONLY_UPDATE = "only_update"
    OVERWRITE = "overwrite"
    REPLACE = "replace"


class RecordMergeMethod:
    """Per-record strategies for merging new values into an existing row.

    Attributes
    ----------
    REPLACE : str
        Overwrite every column with the new values.
    MERGE_NEW_LEADING : str
        New values win, but ``None`` in the new record does **not** clear
        an existing value.
    MERGE_EXISTING_LEADING : str
        Existing values win, but ``None`` in the existing record is
        filled from the new record when available.
    """

    REPLACE = "replace"
    MERGE_NEW_LEADING = "merge_new_leading"
    MERGE_EXISTING_LEADING = "merge_existing_leading"
