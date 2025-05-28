from typing import Any, Dict, Union

from rgs_utils.tasks.validation_logger import ValidationLogger

_registered_classes: dict[str, type["ValidationBaseclass"]] = {}


def do_register_validation(cls: type["ValidationBaseclass"]):
    """Register validation class."""

    name = getattr(cls, "IDENTIFIER", None)
    abstract = True if name is None else False

    if not abstract:
        _registered_classes[name] = cls


class EnumLevel:
    """Enum for error and warning levels in calculations."""

    WARNING = 1
    ERROR = 2
    CRITICAL = 3


class ValidationBaseclass:
    IDENTIFIER = None
    NAME = None
    LEVEL = None
    MESSAGE = None

    # abstract = True
    validation_logger: ValidationLogger

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "abstract", False):
            cls.abstract = False

        do_register_validation(cls)

    def __init__(self, validation_logger: ValidationLogger = None):
        if validation_logger is None:
            validation_logger = ValidationLogger.get_current_logger()

        self.validation_logger = validation_logger

    def log(
        self,
        source_ref,
        object_identifier,
        object_source_ref,
        source_column,
        target_column,
        params: Dict[str, Any] = None,
        fixed: bool = False,
        fix_action: str = None,
        source_id: int = None,
        source_ref_type: str = None,
        target_table_id: str = None,
    ):
        self.validation_logger.log(
            validation_id=self.IDENTIFIER,
            source_ref=source_ref,
            object_identifier=object_identifier,
            object_source_ref=object_source_ref,
            source_column=source_column,
            target_column=target_column,
            params=params,
            fixed=fixed,
            fix_action=fix_action,
            source_id=source_id,
            source_ref_type=source_ref_type,
            target_table_id=target_table_id,
        )
