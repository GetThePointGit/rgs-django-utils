import itertools
import json
from typing import Any, Callable

from rgs_utils.forms.Section import Section
from rgs_utils.models import EnumWorkflowType
from rgs_utils.models.enums import EnumWorkflowStep
from rgs_utils.models.enums.task_status import EnumTaskStatus
from rgs_utils.models.task import Task, Workflow
from rgs_utils.tasks.base_class import WorkflowBase


class WorkflowImportBase(WorkflowBase):
    """Base class for all imports."""

    WORKFLOW_TYPE = EnumWorkflowType.IMPORT
    # list of EnumDataType

    # EnumSourceType
    SOURCE_TYPE = None

    STEPS = [
        EnumWorkflowStep.SOURCE_SELECTION,
        EnumWorkflowStep.IMPORT_CONFIGURATION,
        EnumWorkflowStep.FIELDS_CONFIGURATION,
        EnumWorkflowStep.VALIDATION,
        EnumWorkflowStep.APPROVAL,
        EnumWorkflowStep.IMPORT,
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.SOURCE_TYPE is None:
            raise NotImplementedError(f"SOURCE_TYPE not provided  for {self.__class__.__name__}")

    def process_source_selection(self, user_id, *args, **kwargs):
        raise NotImplementedError("run_source_selection not implemented")

    def process_import_configuration(self, user_id, *args, **kwargs):
        raise NotImplementedError("run_import_configuration not implemented")

    def process_fields_configuration(self, user_id, *args, **kwargs):
        raise NotImplementedError("run_fields_configuration not implemented")

    def process_validation(self, user_id, *args, **kwargs):
        raise NotImplementedError("run_validation not implemented")

    def process_approval(self, user_id, *args, **kwargs):
        raise NotImplementedError("run_approval not implemented")

    def sanitize_request_body(self, request, form) -> dict:
        """Sanitize the configuration of the task.

        Remove all fields that are not in fields. Stringify all values.

        Args:
            request (Request): request object
            sections (list[Section]): fields configured for the workflow by the developer

        Returns:
            dict: sanitized configuration

        """
        json_body: dict[str, Any] = json.loads(request.body)
        # remove all fields that are not in fields

        form.sanitize(json_body)

    @staticmethod
    def validate_config(workflow: Workflow, config: dict, sections: list[Section]) -> tuple[dict, list[str]]:
        """Validate the config against on the given fields.

        Args:
            workflow (Workflow): workflow for which the configuration is parsed
            config (dict): configuration to parse posted by the user
            sections (list[Section]): fields configured for the workflow by the developer

        Returns:
            tuple[dict, list[str]]: parsed configuration and list of errors
        """

        errors: list[str] = []
        parsed_config = {}

        fields = list(field for field in [field for section in sections for field in section.fields])

        for field in fields:
            field.validate()

        errors = list(itertools.chain(*[field.errors for field in fields]))

        return parsed_config, errors

        # for field in fields:
        #     if not field.nullable and field.name not in config:
        #         errors.append(f"field {field.name} is required")
        #     if field["name"] in config:
        #         try:
        #             if field["type"] == "boolean":
        #                 parsed_config[field["name"]] = bool(config.get(field["name"]))
        #             elif field["type"] == "number":
        #                 parsed_config[field["name"]] = int(config.get(field["name"]))
        #             elif field["type"] == "enum":
        #                 if config.get(field["name"]) not in dict(field["choices"]):
        #                     errors.append(f"field {field['name']} has an invalid value")
        #                 else:
        #                     parsed_config[field["name"]] = config.get(field["name"])
        #             elif field["type"] == "string":
        #                 parsed_config[field["name"]] = str(config.get(field["name"]))
        #             elif field["type"] == "upload":
        #                 parsed_config[field["name"]] = int(config.get(field["name"]))
        #                 if not ProjectFile.objects.filter(
        #                     id=parsed_config[field["name"]],
        #                     project=workflow.project,
        #                     file_purpose_id=EnumFilePurpose.IMPORT,
        #                 ).exists():
        #                     errors.append(f"field {field['name']} has an invalid value")
        #             else:
        #                 errors.append(f"field {field['name']} has an invalid type")
        #         except ValueError:
        #             errors.append(f"field {field['name']} has an invalid value")

        # return parsed_config, errors

    @staticmethod
    def queue_task(
        user: Any,
        workflow: Workflow,
        step: EnumWorkflowStep,
        exec_process: Callable[[Task], bool],
        config: dict = {},
        on_success: Callable[[], None] | None = None,
    ):
        task, _ = workflow.tasks.update_or_create(
            step=step,
            defaults=dict(
                last_modified_by=user,
                status_id=EnumTaskStatus.QUEUED,
                config=config,
            ),
            create_defaults=dict(
                created_by=user,
            ),
        )

        def run_task(task):
            successfull = exec_process(task)
            task.refresh_from_db()
            if successfull and callable(on_success):
                on_success()
            else:
                task.status_id = EnumTaskStatus.FAILED
                task.save()

        # run this async, but do not await. How can we make this work?
        run_task(task)

        return task

    @staticmethod
    def set_next_step_status(workflow: Workflow, step: EnumWorkflowStep, status: EnumTaskStatus):
        task = workflow.tasks.get(step=step)
        task.status_id = status
        task.save()
