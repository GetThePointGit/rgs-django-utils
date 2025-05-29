from rgs_django_utils.models.enums import EnumDataType
from rgs_django_utils.tasks.base_class import WorkflowBase


class WorkflowExportBase(WorkflowBase):
    """Base class for all exports."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run_export(self, config, *args, **kwargs):
        raise NotImplementedError("run_export not implemented")
