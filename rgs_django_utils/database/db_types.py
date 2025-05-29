GENERIC_EXCEL = "generic_xlsx"
GENERIC_OGR = "generic_ogr"


class ImportMethod:
    """How to replace or merge records in the database."""

    ONLY_NEW = "only_new"  # only new records will be added, existing records will be ignored.
    ONLY_UPDATE = "only_update"  # only existing records will be updated, new records will be ignored.
    OVERWRITE = "overwrite"  # all records will be overwritten and new records will be added.
    REPLACE = "replace"  # all records will be replaced. Records not in the new data will be deleted.


class RecordMergeMethod:
    """How to merge the data in a record with the existing data in the database."""

    REPLACE = "replace"  # replace the existing data with the new data.
    MERGE_NEW_LEADING = "merge_new_leading"  # merge the new data with the existing data, with the new data leading. None values in the new data will not filled with existing values.
    MERGE_EXISTING_LEADING = "merge_existing_leading"  # merge the new data with the existing data, with the existing data leading. None values in the existing data will be filled with new values.
