from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from django.http import HttpResponse
from ninja import Body, File, Router
from ninja.files import UploadedFile
from pydantic import BaseModel

from rgs_utils.models import EnumTaskStatus, EnumWorkflowStep, EnumWorkflowType, Workflow
from rgs_utils.models.enums.file_purpose import EnumFilePurpose
from rgs_utils.models.task import ProjectFile
from rgs_utils.models.task import Task as TaskModel
from rgs_utils.tasks.base_class import WorkflowBase, get_workflow_template_class, get_workflows_by_file
from rgs_utils.utils.authorization import JwtModuleToken
from rgs_utils.utils.email_template import EmailTemplate
from thissite import settings

task_api = Router(tags=["tasks"])


class Result(BaseModel):
    name: str
    response: dict

    class Config:
        strict = False


class DataCreateWorkflow(BaseModel):
    """Create a workflow."""

    name: Optional[str] = None
    description: Optional[str] = None
    project_id: int
    workflow_type: Optional[EnumWorkflowType.get_enum_class()] = None  # todo: remove?
    workflow_template_id: str


class DataCreateWorkflowWithFile(BaseModel):
    """Create a workflow and use project_file_id as selected source.

    The parameter workflow_template_id is only required if the extenstion of the file file is supported by multiple workflows.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    project_id: int
    workflow_template_id: Optional[str] = None
    project_file_id: int


class TaskStatus(BaseModel):
    step: EnumWorkflowStep.get_enum_class()
    status: EnumTaskStatus.get_enum_class()
    progress: Optional[int]
    progress_text: Optional[str]


class WorkflowStatus(BaseModel):
    # status: EnumTaskStatus.get_enum_class()
    id: int
    name: str
    counts: Optional[dict]
    tasks: list[TaskStatus]


class Logs(BaseModel):
    level: int
    message: str
    obj: str


class Task(BaseModel):
    id: int
    step: EnumWorkflowStep.get_enum_class()
    name: str
    status: EnumTaskStatus.get_enum_class()
    config: dict
    input: dict
    warnings: Optional[list[Logs]]
    errors: Optional[list[Logs]]
    next_step: Optional[list[EnumWorkflowStep.get_enum_class()]]


# todo: define the error
class Error(BaseModel):
    type: str
    message: str


class GlobalError(BaseModel):
    error: str


class FormError(BaseModel):
    errors: Dict[str, List[Error]]


class MinimalTaskResponse(BaseModel):
    workflow_id: int
    task_id: int
    status_id: str
    next_step: str | None
    locked: bool


class TaskResponse(MinimalTaskResponse):
    config: dict | None

    form: Optional[dict]
    form_errors: Optional[Dict[str, List[str]]]
    form_warnings: Optional[Dict[str, List[str]]]

    started: Optional[datetime]
    finished: Optional[datetime]
    output: Any | None
    summary: Optional[Dict[str, Any]]
    counts: Any  # Optional[List[Dict[str, Any]]]

    logs: Optional[List[Dict[str, Any]]]


class ProjectFileResponse(BaseModel):
    id: int
    filename: str
    url: str


class WorkflowOptions(BaseModel):
    message: str
    options: list["WorkflowOption"]


class WorkflowOption(TypedDict):
    name: str
    workflow_template_id: str


@task_api.get("/{int:task_id}/")
def get_task(request, task_id: int):
    """Get task information."""
    user_id = request.user.id if request.user is not request.user.is_anonymous else 0

    task = TaskModel.objects.get(pk=task_id)

    if task.workflow is not None:
        workflow_template = get_workflow_template_class(task.workflow.template.id)
        if not workflow_template.check_permissions("read", user_id, task.workflow.project_id):
            raise PermissionError("No permission to read task information")
    else:
        # TODO: Task has no project_id, how to check permissions?
        if not task.check_permissions("read", user_id):
            raise PermissionError("No permission to read task information")

    return task.task_response()


@task_api.post("/project/{project_id}/upload", response={200: ProjectFileResponse, 400: GlobalError, 403: GlobalError})
def project_file_upload(
    request, project_id: int, file: UploadedFile = File(...)
) -> HttpResponse | ProjectFileResponse:
    """Upload a file to the project."""
    # todo: check permissions
    user_id = request.user.id if not request.user.is_anonymous else 0

    splitted_filename = file.name.split(".")
    if len(splitted_filename) < 2:
        return 400, {"error": "The file has no extension, but it is required."}
    extension = f".{splitted_filename[-1].lower()}"
    if extension not in settings.ALLOWED_FILE_EXTENSIONS:
        return (
            403,
            {
                "error": f"The file has an extension that is not allowed. Please provide a file with one of the following extensions: {', '.join(settings.ALLOWED_FILE_EXTENSIONS)}",
            },
        )

    project_file = ProjectFile.objects.create(
        project_id=project_id,
        filename=file.name,
        created_by_id=user_id,
        last_modified_by_id=user_id,
        file_purpose_id=EnumFilePurpose.IMPORT,
    )

    try:
        with file as stream:
            project_file.file.save(file.name, stream)
    except Exception as e:
        return {"error": str(e)}
    finally:
        if not file.closed:
            file.file.close()

    return ProjectFileResponse(
        **{
            "id": project_file.id,
            "filename": file.name,
            "url": f"/api/tasks/project/{project_id}/file/{project_file.id}",
        }
    )


@task_api.get("/project/{int:project_id}/file/{int:file_id}", response={200: bytes, 404: GlobalError})
def project_file_download(request, project_id: int, file_id: int) -> bytes:
    """Download a file from the project."""
    user_id = request.user.id if not request.user.is_anonymous else 0

    # TODO: check permissions

    project_file = ProjectFile.objects.get(pk=file_id, project_id=project_id)

    with project_file.file.open("rb") as f:
        return HttpResponse(
            status=200,
            content=f.read(),
            content_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={project_file.filename}"},
        )
    return 404, {"error": "File not found"}


def _project_file_upload_start_workflow(
    user_id: int, data: DataCreateWorkflowWithFile
) -> HttpResponse | WorkflowStatus | GlobalError | WorkflowOptions:
    """Start a workflow with the uploaded file."""
    project_file = ProjectFile.objects.get(pk=data.project_file_id, project_id=data.project_id)

    workflow_templates = get_workflows_by_file(user_id, project_file)
    if data.workflow_template_id is not None:
        if data.workflow_template_id not in [
            workflow_template.TEMPLATE_ID for workflow_template in workflow_templates
        ]:
            return 404, {"error": "Workflow template not found for this file."}
        workflow_template = get_workflow_template_class(data.workflow_template_id)
    else:
        if len(workflow_templates) == 0:
            return 404, {"error": "No workflow templates found for this file."}
        if len(workflow_templates) > 1:
            return 422, {
                "message": "There are multiple workflow templates found that could be started with the uploaded file. Retry the request with the workflow_template_id of the desired workflow in the body.",
                "options": [
                    {
                        "name": workflow_template.TEMPLATE_NAME,
                        "workflow_template_id": workflow_template.TEMPLATE_ID,
                    }
                    for workflow_template in workflow_templates
                ],
            }
        workflow_template = workflow_templates[0]

    if not workflow_template.check_permissions("create", user_id, data.project_id):
        raise PermissionError("No permission to create workflow")

    workflow_class: WorkflowBase = workflow_template.create_workflow(
        project_id=data.project_id,
        user_id=user_id,
        name=data.name,
        remarks=data.description,
    )

    workflow_class.autofill_source_selection(
        user_id=user_id,
        project_file_id=data.project_file_id,
    )

    return 201, WorkflowStatus(**workflow_class.response())


@task_api.post("/workflow", response={201: WorkflowStatus, 403: GlobalError, 422: WorkflowOptions, 404: GlobalError})
def create_workflow(request, data: DataCreateWorkflow | DataCreateWorkflowWithFile):
    """Create a new workflow."""
    user_id = request.user.id if not request.user.is_anonymous else 0

    if hasattr(data, "project_file_id"):
        data: DataCreateWorkflowWithFile
        return _project_file_upload_start_workflow(
            user_id=user_id,
            data=data,
        )
    data: DataCreateWorkflow

    workflow_template = get_workflow_template_class(data.workflow_template_id)  # raise

    if not workflow_template.check_permissions("create", user_id, data.project_id):
        raise PermissionError("No permission to create workflow")

    workflow_class = workflow_template.create_workflow(
        project_id=data.project_id,
        user_id=user_id,
        name=workflow_template.TEMPLATE_NAME,
        remarks=data.description,  # remarks same as description?
    )

    return 201, WorkflowStatus(**workflow_class.response())


@task_api.get("/workflow/{workflow_id}")
def get_workflow_status(request, workflow_id: int) -> WorkflowStatus:
    """Get workflow status."""
    workflow = Workflow.objects.get(pk=workflow_id)  # raise
    workflow_class = workflow.workflow_class

    user_id = request.user.id if not request.user.is_anonymous else 0
    if not workflow_class.check_permissions("select", user_id, workflow.project_id):
        raise PermissionError("No permission to get workflow information")

    return WorkflowStatus(**workflow_class.response())


@task_api.get("/workflow/{workflow_id}/api/routes")
def get_workflow_custom_api_routes(request, workflow_id: int) -> dict[str, str]:
    """Get workflow status."""
    workflow = Workflow.objects.get(pk=workflow_id)  # raise
    workflow_class = workflow.workflow_class

    user_id = request.user.id if not request.user.is_anonymous else 0
    if not workflow_class.check_permissions("select", user_id, workflow.project_id):
        raise PermissionError("No permission to get workflow information")

    return workflow_class.api_routes()


@task_api.get("/workflow/{workflow_id}/api/{api_id}")
def get_workflow_custom_api(request, workflow_id: int, api_id: str) -> any:
    """Get result from custom api.

    see /workflow/{workflow_id}/api/routes for available routes and description
    """
    workflow = Workflow.objects.get(pk=workflow_id)  # raise
    workflow_class = workflow.workflow_class

    user_id = request.user.id if not request.user.is_anonymous else 0
    if not workflow_class.check_permissions("select", user_id, workflow.project_id):
        raise PermissionError("No permission to get workflow information")

    return workflow_class.call_to_api(request, api_id)


responseCodes = {
    200: MinimalTaskResponse | TaskResponse,
    201: MinimalTaskResponse,
    400: FormError,
    401: GlobalError,
    403: GlobalError,
    404: GlobalError,
    409: GlobalError,
    500: GlobalError,
    501: GlobalError,
}


@task_api.get("/workflow/{int:workflow_id}/step/{str:step}", response=responseCodes)
def get_workflow_step(request, workflow_id: int, step: str):
    """Get workflow step."""
    workflow = Workflow.objects.get(pk=workflow_id)  # raise
    workflow_class = workflow.workflow_class

    user_id = request.user.id if not request.user.is_anonymous else 0

    return workflow_class.api_process_get(step, user_id, request)


@task_api.post("/workflow/{int:workflow_id}/step/{str:step}", response=responseCodes)
def post_workflow_step(request, workflow_id: int, step: str, item: dict = Body(...)):
    """Get workflow step."""
    workflow = Workflow.objects.get(pk=workflow_id)  # raise
    workflow_class = workflow.workflow_class

    user_id = request.user.id if not request.user.is_anonymous else 0

    return workflow_class.api_process_post(step, user_id, request, item)


@task_api.post(
    "send_email/{str:template_name}",
    response={200: dict, 401: GlobalError, 403: GlobalError, 500: GlobalError},
    auth=JwtModuleToken("module_auth_2"),
)
def send_email(request, template_name: str, item: dict = Body(...)):
    """Send email."""
    claims = request.auth
    try:
        EmailTemplate.getByName(template_name).construct(context=item, claims=claims, request=request).send()
    except Exception as e:
        return 500, {"error": "Failed to send email"}
    else:
        return 200, {"message": "Email sent successfully"}
