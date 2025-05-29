from contextvars import ContextVar

import pandas as pd

_current_validation_logger = ContextVar("current_validation_logger")


class ValidationLogger:
    def __init__(self):
        self.validation_logs = []
        self.source_id = None
        self.source_ref_type = None
        self.target_table_id = None

    def set_as_current_logger(self):
        _current_validation_logger.set(self)

    def unset_as_current_logger(self):
        _current_validation_logger.set(None)

    @classmethod
    def get_current_logger(cls):
        return _current_validation_logger.get()

    def set_context(
        self,
        source_id: int,
        source_ref_type: str,
        target_table_id: str,
    ):
        self.source_id = source_id
        self.source_ref_type = source_ref_type
        self.target_table_id = target_table_id

    def get_df(self):
        return pd.DataFrame(
            columns=[
                "validation_id",
                "source_id",
                "source_ref_type",
                "source_ref",
                "source_column",
                "object_identifier",  # bijvoorbeeld de ids
                "object_source_ref",  # ?? bijvoorbeeld begin regelnummer van het object --> weg
                "target_table_id",
                "target_column",
                "params",
                "fixed",  # ja/ nee
                "fix_action",  # welke actie is ondernomen
            ],
            data=self.validation_logs,
        )

    def log(
        self,
        validation_id,
        source_ref,
        source_column,
        object_identifier,
        object_source_ref,
        target_column,
        params,
        fixed: bool = False,
        fix_action: str = None,
        source_id: int = None,
        source_ref_type: str = None,
        target_table_id: str = None,
    ):
        if source_id is not None:
            source_id = self.source_id
        if source_ref_type is not None:
            source_ref_type = self.source_ref_type
        if target_table_id is not None:
            target_table_id = self.target_table_id

        self.validation_logs.append(
            {
                "validation_id": validation_id,
                "source_id": source_id,
                "source_ref_type": source_ref_type,
                "source_ref": source_ref,
                "source_column": source_column,
                "object_identifier": object_identifier,
                "object_source_ref": object_source_ref,
                "target_table_id": target_table_id,
                "target_column": target_column,
                "params": params,
                "fixed": fixed,
                "fix_action": fix_action,
            }
        )
