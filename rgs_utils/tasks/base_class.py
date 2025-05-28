import logging
from datetime import datetime
from typing import Callable, NamedTuple, Type

from ninja import Body
from rgs_utils.forms.Form import Form
from rgs_utils.models import EnumDataType, EnumSourceType, EnumTaskStatus, EnumWorkflowStep
from rgs_utils.models.task import ProjectFile, Task, Workflow
from rgs_utils.tasks.workflow_service_queue import WorkflowServiceQueue

_registered_classes: dict[str, type["WorkflowBase"]] = {}

log = logging.getLogger(__name__)


class SharedWorkflowMethod(NamedTuple):
    """Define the shared method of a workflow step that can be called from the service worker."""

    step_id: str
    """EnumWorkflowStep: The step the shared method belongs to."""
    method: Callable[["WorkflowBase", int, int], None]
    """Callable[[int, int]]: The method to call. Parameters are user_id and workflow_id."""
    requires_user_input: bool
    """EnumWorkflowStep: If False, this step in the workflow will be automatically run after all previous methods are successfully executed."""


class WorkflowBase(object):
    """Base class for all task classes (imports, exports, processing).

    With API routes, for specific request for the forms
    """

    subclasses = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.subclasses.append(cls)
        workflow_register(cls)

    # EnumTaskType
    WORKFLOW_TYPE = None
    # User roles with access to this task
    ACCESS_BY = []

    TEMPLATE_ID: str = None
    TEMPLATE_NAME: str = None
    TEMPLATE_DESCRIPTION: str = None

    MODULES = []

    FOR_DATA_TYPES = [
        EnumDataType.PROJECT,
        EnumDataType.WATERWAY,
        EnumDataType.WATERWAY_LEGGER,
        EnumDataType.WATERWAY_ASSESSMENT,
        EnumDataType.PROFILE_LOCATION,
        EnumDataType.PROFILE_LEGGER,
        EnumDataType.PROFILE_MEASUREMENT,
        EnumDataType.PROFILE_MEASUREMENT_BORING,
        EnumDataType.POINT_MEASUREMENT,
        EnumDataType.SAMPLE_SECTION,
        EnumDataType.BORING,
        EnumDataType.CONTAINER,
        EnumDataType.OBJECT,
        EnumDataType.NOTE,
        EnumDataType.PHOTO,
        EnumDataType.REMARK,
    ]

    STEPS = [EnumWorkflowStep.DEFAULT]

    STEPS_WITHOUT_USER_INPUT = []

    SOURCE_TYPE = None

    FILE_EXTENSIONS = []

    _workflow = None

    def __init__(self, workflow_id: int = None, workflow=None):
        self.workflow_id = workflow_id
        self.workflow = workflow

        if self.TEMPLATE_ID is None:
            raise NotImplementedError(f"TEMPLATE_ID not provided for {self.__class__.__name__}")
        if self.TEMPLATE_NAME is None:
            raise NotImplementedError(f"TEMPLATE_NAME not provided for {self.__class__.__name__}")
        if self.MODULES is None:
            raise NotImplementedError(f"MODULES not provided for {self.__class__.__name__}")

    @classmethod
    def get_shared_method_for_step(cls, step_id: str) -> SharedWorkflowMethod:
        """Get the shared method for a step.

        Args:
            step_id (str): The step for which the method is defined.
        """

        return SharedWorkflowMethod(
            step_id=step_id,
            method=getattr(cls, f"process_{step_id}"),
            requires_user_input=step_id not in cls.STEPS_WITHOUT_USER_INPUT,
        )

    @classmethod
    def create_workflow(cls, project_id, user_id=None, name=None, remarks=None):
        """Create a new workflow class with underlying workflow model instance."""
        workflow = Workflow.objects.create(
            project_id=project_id,
            template_id=cls.TEMPLATE_ID,
            created_by_id=user_id,
            last_modified_by_id=user_id,
            # step=cls.get_step_index(cls.STEPS[0]),
            name=name or cls.TEMPLATE_NAME,
            remarks=remarks,
        )

        workflow_class = cls(workflow=workflow)

        for step in cls.STEPS:
            workflow.tasks.create(
                step_id=step,
                status_id=EnumTaskStatus.NOT_STARTED,
                created_by_id=user_id,
                last_modified_by_id=user_id,
            )

        first_step_id = next(iter(cls.STEPS), None)
        try:
            active_task = workflow.tasks.get(step_id=first_step_id)
        except Task.DoesNotExist:
            pass
        else:
            active_task.last_modified_by_id = user_id
            active_task.last_modified_at = datetime.now()
            if first_step_id not in cls.STEPS_WITHOUT_USER_INPUT:
                active_task.status_id = EnumTaskStatus.NOT_STARTED  # TODO: auto start?
            else:
                active_task.status_id = EnumTaskStatus.WAIT_FOR_USER_INPUT
            active_task.save()

        workflow.active_step = workflow.tasks.get(step_id=first_step_id)
        workflow.save()

        return workflow_class

    def get_form(self, task) -> Form | None:
        """Return the fields for the api."""
        get_form_ = getattr(self, f"get_{task.step_id}_form", None)
        return get_form_() if get_form_ is not None else None

    def response(self):
        """Return the response for the api."""

        return {
            # "status": self.workflow.status_id,
            "id": self.workflow.id,
            "name": self.workflow.name,
            "counts": self.workflow.counts,
            "tasks": [
                {
                    "step": task.step_id,
                    "status": task.status_id,
                    "progress": task.progress.progress if task.status == EnumTaskStatus.IN_PROGRESS else None,
                    "progress_text": task.progress.description if task.status == EnumTaskStatus.IN_PROGRESS else None,
                }
                for task in self.workflow.tasks.all()
            ],
        }

    @property
    def workflow(self) -> Workflow:
        if self.workflow_id is None:
            raise ValueError("workflow_id not set")

        if self._workflow is None:
            self._workflow = Workflow.objects.get(pk=self.workflow_id)
        return self._workflow

    @workflow.setter
    def workflow(self, workflow: Workflow):
        self._workflow = workflow
        self.workflow_id = workflow.id
        # check if types are equal

    def call_to_api(self, request, api_name, *args, **kwargs):
        """Call an api function by name."""
        # todo: authorization

        api_function = "api_" + api_name

        api_func = getattr(self, api_function, None)
        if api_func is None:
            raise ValueError(f"api function {api_function} not found")
        return api_func(request, *args, **kwargs)

    def api_routes(self):
        """Returns api endpoints (key) and the function description (value)."""
        # all api routes for this class are functions starting with 'api_<route_name>'
        routes = [f for f in dir(self) if f.startswith("api_")]
        return {r[4:]: getattr(self, r).__doc__ for r in routes}

    @classmethod
    def api_info(cls, request, *args, **kwargs):
        """Returns the info of this processing class."""

        return {
            "template_id": cls.TEMPLATE_ID,
            "template_name": cls.TEMPLATE_NAME,
            "template_description": cls.TEMPLATE_DESCRIPTION,
            "source_type": cls.SOURCE_TYPE,
            "name": cls.__class__.__name__,
            "docstring": cls.__doc__,
        }

    @classmethod
    def check_permissions(cls, action, user_id, project_id):
        """Check if the user has the right permissions for the action.

        :param action: str: action to check
        :param user_id: int: user id
        :param project_id: int: project id
        :return: Workflow: workflow object
        """
        # todo: check permissions
        return True

    @classmethod
    def get_step_index(cls, step_id: str):
        return cls.STEPS.index(step_id)

    @classmethod
    def has_step(cls, step_id: str):
        return step_id in cls.STEPS

    @classmethod
    def get_next_step(cls, step_id: str) -> str | None:
        index = cls.STEPS.index(step_id)
        index += 1
        return next(iter(cls.STEPS[index:]), None)

    def update_task_status(
        self,
        step,
        status,
    ):
        task = self.workflow.tasks.get(
            step=step,
        )

        task.status = status
        task.save()
        return task

    @classmethod
    def exec_shared_method(cls, user, workflow, method):
        if method not in cls.SHARED_METHODS:
            raise ValueError(f"Method {method} not found in shared tasks")
        cls[method](user, workflow)

    def queue_shared_method_of_step(
        self,
        user_id: int,
        step_id: str,
        config: dict,
        run_sync: bool = False,
    ) -> Task:
        """Queue the shared method of given step for the service worker to deal with.
        Also sets the task status to QUEUED and saves the configuration in the task.config field.
        The configuration of the shared method must be returned by the get_shared_method_for_step method when the given step is passed to it.

        However if run_sync is set to True, the shared method is executed synchronously.
        The tasks that immidiately follow this task and do not require user input will still be executed asynchronously.
        This can be useful in a workflow. For example one can have a configuration step that require user input (and save it synchronously), followed by complex computation steps that are run asynchronously which use the saved user input.

        Args:
            user_id (int): User ID that queued the workflow step
            step_id (str): Step of which to execute the shared method
            config (dict): Configuration for the task. It is stored in the task.config field and not passed into the queue.
            run_sync (bool): If True, the shared method is executed synchronously. Default is False.

        Raises:
            NotImplementedError: If the step is not implemented in the workflow.
            ValueError: If the task is not found.

        Returns:
            Task: The task that was queued.
        """
        if not self.has_step(step_id):
            raise NotImplementedError(f"Step {step_id} not implemented in workflow {self.__name__}")
        try:
            task: Task = self.workflow.tasks.get(step_id=step_id)
        except Task.DoesNotExist:
            raise ValueError(f"Task for workflow {self.workflow.id} and step {step_id} not found")

        self.workflow.active_step = task
        self.workflow.save()
        task.activate(user_id)
        task.status_id = EnumTaskStatus.QUEUED
        task.config = config
        task.save()

        WorkflowServiceQueue.get_instance().queue_workflow_method(
            user_id=user_id,
            workflow_id=self.workflow.id,
            step_id=step_id,
            run_sync=run_sync,
        )

        if run_sync:
            self.workflow.refresh_from_db()
            task.refresh_from_db()
        else:
            task.logs.create(
                level=logging.INFO,
                message="De taak is in de wachtrij geplaatst.",
            )

        return task

    @classmethod
    def file_compatible(cls, extension: str, first_100_bytes_of_file: bytes) -> int:
        """Check if the file is compatible with the task.

        Args:
            extension (str): The extension of the file.
            first_100_bytes_of_file (str): The first 100 characters of the file.

        Returns:
            int: The compatibility score. The higher the score, the more compatible the file is with the task.
        """
        raise NotImplementedError("file_compatible not implemented")

    @classmethod
    def autofill_source_selection(
        cls,
        user_id: int,
        workflow: Workflow,
        project_file_id: int,
        *args,
        **kwargs,
    ):
        """Automatically fill the source selection step of the workflow.

        Args:
            user_id (int): User ID that queued the workflow step
            workflow (Workflow): Workflow instance
            project_file_id (int): The ID of the uploaded file.
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        raise NotImplementedError("auto_fill_source_selection not implemented")

    def api_process_get(self, step: str, user_id: int, request):
        if not self.check_permissions("select", user_id, self.workflow.project_id):
            return 403, {"error": "No permission to get workflow information"}

        if step not in self.STEPS:
            return 404, {"error": f"Step {step} not found in workflow {self.__class__.__name__}"}

        try:
            return getattr(self, f"get_{step}")(request, user_id)
        except AttributeError:
            return 501, {"error": f"get_{step} not implemented in {self.__class__.__name__}"}
        except Exception as e:
            log.exception(f"Error in {self.__class__.__name__} get_{step}")
            return 500, {"error": str(e)}

    def api_process_post(self, step: str, user_id: int, request, item: dict = Body(...)):
        """Process the post step of the workflow. called from the api."""

        if not self.check_permissions("select", user_id, self.workflow.project_id):
            return 403, {"error": "No permission to post workflow information"}

        if step not in self.STEPS:
            return 404, {"error": f"Step {step} not found in workflow {self.__class__.__name__}"}

        if self.workflow.has_running_tasks:
            return 409, {"error": "there is already a task running"}
        if not self.workflow.previous_tasks_are_completed(step_id=step):
            return 409, {"error": "previous steps not done"}

        try:
            return getattr(self, f"post_{step}")(request, item)
        except AttributeError:
            return 501, {"error": f"post_{step} not implemented in {self.__class__.__name__}"}
        except Exception as e:
            log.exception(f"Error in {self.__class__.__name__} post_{step}")
            return 500, {"error": f"Error in {self.__class__.__name__} post_{step}: {e}"}


def get_workflow_template_class(name: str) -> Type[WorkflowBase]:
    try:
        return _registered_classes[name]
    except KeyError:
        raise ValueError(f"Class {name} not found")


def workflow_register(cls: Type[WorkflowBase]):
    """Register all task classes."""

    name = getattr(cls, "TEMPLATE_ID", None)
    abstract = True if name is None else False

    if not abstract:
        _registered_classes[name] = cls


def get_workflows_by_file(user_id: int, file: ProjectFile) -> list[type[WorkflowBase]]:
    """Get the workflows that best matches the file."""
    workflow_templates = [
        class_
        for class_ in _registered_classes.values()
        if class_.SOURCE_TYPE == EnumSourceType.FILE and class_.check_permissions("create", user_id, file.project_id)
    ]
    first_100_bytes_of_file = file.first_100_bytes()
    extension = file.filename.split(".")[-1].lower()
    workflow_template_scores = [
        workflow_template for workflow_template in workflow_templates if extension in workflow_template.FILE_EXTENSIONS
    ]
    workflow_template_scores.sort(
        key=lambda workflow_template: workflow_template.file_compatible(extension, first_100_bytes_of_file),
        reverse=True,
    )
    return workflow_template_scores
