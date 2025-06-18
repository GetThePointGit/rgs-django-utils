import logging
import os
import typing
from datetime import datetime

import psutil
from django.conf import settings

from rgs_django_utils import logging as custom_logging
from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models import ModificationMetaMixin
from rgs_django_utils.database.dj_extended_models import Config
from rgs_django_utils.models import EnumDataType, EnumWorkflowStep, enums
from rgs_django_utils.models.enums.role import EnumRole
from rgs_django_utils.models.enums.task_status import EnumTaskStatus

if typing.TYPE_CHECKING:
    from rgs_django_utils.tasks.base_class import WorkflowBase


section_task = models.TableSection("task", "taken", 800, "Import, export en processing gerelateerde modellen")

__all__ = [
    "WorkflowTemplate",
    "Workflow",
    "Task",
    "TaskLog",
    "TaskProgress",
    "WorkflowDataLog",
]

log = logging.getLogger(__name__)


# todo: expect a table "Project" and "Selection"
project_table = getattr(settings, "PROJECT_MODEL", "core.Project")
selection_table = getattr(settings, "SELECTION_MODEL", "core.Selection")


class WorkflowTemplate(models.Model):
    id = models.TextField(
        "identification",
        primary_key=True,
        config=models.Config(
            doc_short="identificatiecode",
            doc_development="given in the django class name",
        ),
    )

    name = models.TextField(
        "naam",
        config=models.Config(
            doc_short="Naam",
        ),
    )
    description = models.TextField(
        "omschrijving",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Omschrijving van de import",
        ),
    )

    workflow_type = models.ForeignKey(
        enums.EnumWorkflowType,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="type",
        config=models.Config(
            doc_short="Type van de import",
        ),
    )

    access_by = models.ArrayField(
        models.TextField(),
        verbose_name="toegankelijk voor",
        db_default=f"{{'{EnumRole.DEVELOPER}'}}",
    )

    modules = models.ArrayField(
        models.TextField(),
        verbose_name="modules",
        db_default="{}",
    )

    for_data_types = models.ArrayField(
        models.TextField(),
        verbose_name="modules",
        db_default=f"{{'{EnumDataType.PROJECT}'}}",
    )

    source_type = models.ForeignKey(
        "EnumSourceType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="bron type",
        config=models.Config(
            doc_short="soort bron, alleen voor imports",
        ),
    )
    steps = models.ArrayField(
        models.TextField(),
        verbose_name="stappen",
        db_default="{}",
    )

    class Meta:
        db_table = "workflow_template"
        verbose_name = "workflow template"
        verbose_name_plural = "workflow templates"

    class TableDescription:
        section = section_task
        order = 1
        description = "workflow template is een geprogrammeerde workflow, zoals een import, export of verwerking"

    def __str__(self):
        return f"{self.workflow_type_id} - {self.ids} - {self.name}"

    def get_next_step(self, current_step):
        """Get the next step in the workflow."""
        try:
            index = self.steps.index(current_step)
            return self.steps[index + 1]
        except ValueError:
            return None

    @classmethod
    def default_records(cls):
        from django.apps import apps

        from rgs_django_utils.tasks.base_class import _registered_classes

        # load for all django apps the tasks classes
        for name, app in apps.app_configs.items():
            app_path = app.module.__path__[0]
            tasks_path = os.path.join(app_path, "tasks")

            if os.path.isdir(tasks_path) or os.path.isfile(tasks_path + ".py"):
                __import__(f"{app.name}.tasks")

        data = []
        for mods in _registered_classes.values():
            data.append(
                (
                    mods.TEMPLATE_ID,
                    mods.TEMPLATE_NAME,
                    mods.TEMPLATE_DESCRIPTION,
                    mods.WORKFLOW_TYPE,
                    mods.ACCESS_BY,
                    mods.MODULES,
                    mods.FOR_DATA_TYPES,
                    mods.STEPS,
                    mods.SOURCE_TYPE,
                )
            )

        return dict(
            fields=[
                "id",
                "name",
                "description",
                "workflow_type_id",
                "access_by",
                "modules",
                "for_data_types",
                "steps",
                "source_type_id",
            ],
            data=data,
        )


class ProjectFile(ModificationMetaMixin):
    """Upload or Export File."""

    id = models.BigAutoField(
        primary_key=True,
    )

    project = models.ForeignKey(
        project_table,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="project",
        config=models.Config(
            doc_short="project waar de upload betrekking op heeft",
        ),
    )
    uuid = models.UUIDField(
        db_default=models.Func(function="uuid7"),
        config=models.Config(
            doc_short="unieke identificatie van de upload",
        ),
    )

    filename = models.TextField(
        "bestandsnaam",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="naam van het bestand",
        ),
    )
    file_purpose = models.ForeignKey(
        enums.EnumFilePurpose,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="bestandsdoel",
        config=models.Config(
            doc_short="doel van het bestand, zoals import, export, projectwerkwijze, etc.",
        ),
    )

    remarks = models.TextField(
        "opmerkingen",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Opmerkingen over de upload",
        ),
    )

    file = models.FileField(
        null=True,
        blank=True,
        config=models.Config(
            doc_short="upload bestand",
        ),
    )

    class Meta:
        db_table = "project_file"
        verbose_name = "project bestand"
        verbose_name_plural = "project bestanden"

    class TableDescription:
        section = section_task
        order = 2
        description = "Bestand behorende bij een project"

    def __str__(self):
        return f"{self.__class__.__name__}: pid {self.project_id} - {self.filename}"

    def first_100_bytes(self) -> typing.Optional[bytes]:
        if self.file:
            with self.file.open("rb") as f:
                return f.read(100)
        return None


class Workflow(ModificationMetaMixin):
    template = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.CASCADE,
        related_name="+",
        editable=False,
    )

    project = models.ForeignKey(
        project_table,
        on_delete=models.CASCADE,
        related_name="+",
        editable=False,
    )

    uuid = models.UUIDField(
        db_default=models.Func(function="uuid7"),
        editable=False,
        config=Config(
            doc_short="Unieke identificatie van de import",
        ),
    )

    # info van en voor gebruiker
    name = models.TextField(
        "naam",
        null=True,
        blank=True,
        config=Config(
            doc_short="Naam van import, bestaande uit soort import en bron",
            doc_development="Zorg dat dit een combinatie is van het soort import en de bron. "
            "Wordt gebruikt in het overzicht",
        ),
    )
    remarks = models.TextField(
        "opmerkingen",
        null=True,
        blank=True,
        config=Config(
            doc_short="Opmerkingen over de import, door gebruiker in te vullen (als naslag)",
        ),
    )

    active_step = models.ForeignKey(
        "Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="actieve stap",
        config=Config(
            doc_short="Actieve stap in de workflow",
        ),
    )

    locked = models.BooleanField(
        default=False,
        config=Config(
            doc_short="Taak is gelocked en kan niet meer worden aangepast",
        ),
    )

    # configuration in the subtasks of this workflow

    # based_on = models.ForeignKey(
    #     'self',
    #     on_delete=models.SET_NULL,
    #     null=True, blank=True,
    #     related_name='basis voor',
    #     verbose_name='gebaseerd op',
    #     config=Config(
    #         doc_short="Gerelateerde import of export",
    #     )
    # )

    selection = models.ForeignKey(
        selection_table,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        config=Config(
            doc_short="Selectie van objecten die geëxporteerd worden",
        ),
    )
    proj_file = models.ForeignKey(
        ProjectFile,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        config=Config(
            doc_short="geüpload bestand",
        ),
    )

    # outcome
    db_execution_dt = models.DateTimeField(
        "datum verwerking in database",
        null=True,
        blank=True,
        config=Config(
            doc_short="Tijdstip van de uiteindelijk verwerking van de data in de database",
        ),
    )

    counts = models.JSONField(
        "aantallen",
        null=True,
        blank=True,
        config=Config(
            doc_short="Aantallen toegevoegde en geupdate records",
        ),
    )

    summary = models.JSONField(
        "samenvatting",
        null=True,
        blank=True,
        config=Config(
            doc_short="Samenvatting van de workflow",
            doc_development="Samenvatting vanuit de stappen (deze kunnen verwijderd worden op termijn)",
        ),
    )

    class Meta:
        db_table = "workflow"
        verbose_name = "workflow"
        verbose_name_plural = "workflows"

    class TableDescription:
        section = section_task
        db_install_order = 2
        order = 2
        description = "Uitvoering van een workflow_template: de run van een import, export of verwerking"

    class Triggers:
        pre = ["db_last_modified"]

    def __str__(self):
        return f"{self.__class__.__name__}: pid {self.project_id} - {self.workflow_id} - {self.name}"

    @property
    def workflow_class(self) -> "WorkflowBase":
        from rgs_django_utils.tasks.base_class import get_workflow_template_class

        template = get_workflow_template_class(self.template_id)
        workflow_class = template(workflow=self)
        return workflow_class

    def activate_step(self, user_id, step_id: str) -> None:
        """Activate a task in the workflow.

        Sets the active step to the given step. If the step was not active before the method call all logs will be cleared.

        Resets all later steps in the workflow to NOT_STARTED and clears their logs.
        """
        task: Task = self.tasks.get(step_id=step_id)
        task.activate(user_id)

    @property
    def has_running_tasks(self) -> bool:
        """Check if there are tasks in progress.

        Returns:
            bool: True if there are tasks in progress, False otherwise
        """
        return self.tasks.filter(
            status_id=EnumTaskStatus.IN_PROGRESS,
        ).exists()

    def previous_tasks_are_completed(self, step_id: str) -> bool:
        """Check if all previous tasks are completed.

        Args:
            step_id (str): step id to check for

        Returns:
            bool: True if all previous tasks are completed, False otherwise
        """
        workflow_class = self.workflow_class
        index = workflow_class.STEPS.index(step_id)

        return self.tasks.filter(
            step__in=list(workflow_class.STEPS[:index]),
            status_id__in=[EnumTaskStatus.COMPLETED, EnumTaskStatus.COMPLETED_WITH_WARNINGS],
        ).count() == len(workflow_class.STEPS[:index])


class Task(ModificationMetaMixin):
    """Task execution. Is about the actual execution of a task, especially useful for monitoring and analyses of tasks.

    Actual information, relevant for users are in TaskImport, TaskExport and TaskProcessing

    Task part keeps track of execution (progress, task logging, performance, etc.)
    Task could be deleted after some time (successful exports will be kept for reference. Imports do not depend
     on task)
     Task has generic relation to his 'owner' (project, user, etc.).
    """

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, null=True, blank=True, related_name="tasks")

    step = models.ForeignKey(
        enums.EnumWorkflowStep,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="stap",
        config=Config(
            doc_short="Stap in het workflow proces",
        ),
    )

    log_level = models.IntegerField(default=custom_logging.DATA_INFO)
    started = models.DateTimeField(null=True, blank=True)
    finished = models.DateTimeField(null=True, blank=True)

    status = models.ForeignKey(
        enums.EnumTaskStatus,
        on_delete=models.PROTECT,
        default=enums.EnumTaskStatus.NOT_STARTED,
        related_name="+",
        verbose_name="status",
        config=Config(
            doc_short="Status van de uitvoering van de taak (het proces)",
        ),
    )

    # meta information
    max_memory_usage = models.IntegerField(
        null=True,
        blank=True,
        config=Config(
            doc_unit="MB",
            doc_short="Maximaal geheugengebruik",
        ),
    )
    running_on = models.TextField(
        null=True,
        blank=True,
        config=Config(
            doc_short="Server en process (web/ task) waar de taak op draait",
        ),
    )

    config = models.JSONField(
        "configuratie",
        null=True,
        blank=True,
        config=Config(
            doc_short="Configuratie van de taak",
        ),
    )
    output = models.JSONField(
        "output",
        null=True,
        blank=True,
        config=Config(
            doc_short="output of the processing",
        ),
    )

    class Meta:
        db_table = "task"
        verbose_name = "taak"
        verbose_name_plural = "taak"

    class TableDescription:
        section = section_task
        order = 2
        description = "Uitvoering van een taak"

    class CalculatedFields:
        duration = "finished - started"

    def __str__(self):
        return f"{self.task_id} - {self.name} - {self.created} - {self.status}"

    @property
    def progress_link(self):
        try:
            return self.progress
        except TaskProgress.DoesNotExist:
            self.progress = TaskProgress.objects.create(task=self)
            return self.progress

    @staticmethod
    def get_current_memory_usage():
        """Get current memory usage of the process in MB."""
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

    def update_max_memory_usage(self):
        """Update max memory usage if current memory usage is higher.

        returns: bool, True if max memory usage is updated, False otherwise
        """
        current_memory_usage = self.get_current_memory_usage()
        if self.max_memory_usage is None or current_memory_usage > self.max_memory_usage:
            self.max_memory_usage = current_memory_usage
            return True
        return False

    @property
    def url(self):
        if self.workflow is not None:
            return f"/api/tasks/workflow/{self.workflow_id}/step/{self.step_id}"
        else:
            return f"/api/tasks/{self.id}/"

    def minimal_task_response(self):
        return {
            "workflow_id": self.workflow_id,
            "task_id": self.id,
            "status_id": self.status_id,
            "next_step": self.workflow.workflow_class.get_next_step(self.step_id) if self.workflow else None,
            "locked": self.workflow.locked,
        }

    def task_response(self, form=None, form_errors=None, form_warnings=None):
        out = {
            **self.minimal_task_response(),
            "config": self.config,
            # custom form input/ output
            "form": form,
            "form_errors": form_errors,  # ??
            "form_warnings": form_warnings,  # ??
            # outputs
            "started": self.started,
            "finished": self.finished,
            "output": self.output,
            "counts": self.workflow.counts,
            "summary": self.workflow.summary,
            "logs": self.logs.filter(level__gte=logging.INFO).values(
                "dt",
                "level",
                "message",
                "name",
                "obj",
            ),
        }
        return out

    def clean_logs(self):
        self.logs.all().delete()

    def activate(self, user_id: int) -> None:
        """Activate this task in the workflow.

        Sets the active step to this task. If the step was not active before this method call then all logs will be cleared.

        Resets all later steps in the workflow to NOT_STARTED and clears their logs.
        If the task is not part of a workflow this method does nothing.

        Args:
            user_id (int): user activating the task
        """
        self.workflow: Workflow
        self.workflow.refresh_from_db()

        self.reset_later_tasks(user_id)

        self.clean_logs()

        self.last_modified_by_id = user_id
        self.last_modified_at = datetime.now()
        self.save()

        if (
            self.workflow is None
            or self.workflow.active_step is None
            or self.workflow.active_step.step_id == self.step_id
        ):
            return

        self.workflow.active_step = self
        self.workflow.save()

    def reset_later_tasks(self, user_id: int):
        """Reset all tasks after the current step in a workflow.

        Sets the status of all tasks after the current step to NOT_STARTED and clears their logs.
        If the task is not part of a workflow this method does nothing.

        Args:
            user_id (int): user resetting the tasks
        """
        self.workflow: Workflow
        if self.workflow is None:
            return

        if self.workflow.locked:
            log.warning("Workflow is locked, tasks cannot be reset.")

        workflow_class = self.workflow.workflow_class
        if workflow_class is None:
            return

        index = workflow_class.STEPS.index(self.step_id)
        reset_steps = workflow_class.STEPS[index:]
        later_tasks = self.workflow.tasks.filter(
            step__in=reset_steps,
        )

        for task in later_tasks:
            task.status_id = EnumTaskStatus.NOT_STARTED
            task.started = None
            task.finished = None
            task.last_modified_by_id = user_id
            task.last_modified_at = datetime.now()
            task.clean_logs()
            task.save()

        if EnumWorkflowStep.VALIDATION in reset_steps:
            self.workflow.datalogs.all().delete()


class TaskLog(models.Model):
    id = models.BigAutoField(
        primary_key=True,
    )

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="logs",
        editable=False,
    )
    dt = models.DateTimeField(auto_now_add=True)

    level = models.IntegerField(
        default=logging.INFO,
        config=Config(
            doc_short="Log niveau",
        ),
    )
    message = models.TextField(
        "bericht",
        config=Config(
            doc_short="Bericht van de log",
        ),
    )

    name = models.TextStringField(
        "naam",
        config=Config(
            doc_short="Naam van de logger (bijvoorbeeld de functie of module)",
        ),
    )
    obj = models.TextStringField(
        "object",
        null=True,
        blank=True,
        config=Config(
            doc_short="Object waar de log betrekking op heeft",
        ),
    )
    extra = models.JSONField(
        "extra",
        null=True,
        blank=True,
        config=Config(
            doc_short="Extra informatie van de log",
        ),
    )

    class Meta:
        db_table = "task_log"
        verbose_name = "taak log"
        verbose_name_plural = "taak logs"

    class TableDescription:
        section = section_task
        order = 3
        description = "Log van de taak"

    def __str__(self):
        return f"{self.dt} - {self.dt} - {self.message}"


class TaskProgress(models.Model):
    """Progress of a task.

    Separate table, because this could change in high frequency (better in combination with description).
    """

    task = models.OneToOneField(
        Task,
        primary_key=True,
        db_column="id",
        on_delete=models.CASCADE,
        related_name="progress",
        editable=False,
    )
    description = models.TextField(
        "beschrijving",
        default="Nog niet gestart...",
        config=Config(
            doc_short="Naam van de taak die momenteel wordt uitgevoerd",
        ),
    )
    progress = models.IntegerField(
        "voortgang",
        default=0,
        config=Config(
            doc_unit="%",
            doc_short="Voortgang van de taak in procenten",
        ),
    )
    db_last_modified = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "task_progress"
        verbose_name = "taak voortgang"
        verbose_name_plural = "taak voortgangen"

    class TableDescription:
        section = section_task
        order = 4
        description = "Voortgang van de taak"

    class Triggers:
        pre = ["db_last_modified"]

    def __str__(self):
        return f"task status {self.description} {self.progress}%"


class WorkflowDataLog(models.Model):
    id = models.BigAutoField(
        primary_key=True,
    )

    workflow = models.ForeignKey(
        Workflow,
        on_delete=models.CASCADE,
        related_name="datalogs",
        editable=False,
    )
    dt = models.DateTimeField(auto_now_add=True)

    level = models.IntegerField(
        default=logging.INFO,
        config=Config(
            doc_short="Log niveau",
        ),
    )

    obj_type = models.ForeignKey(
        enums.EnumSourceType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        config=Config(
            doc_short="Type van het object waar de log betrekking op heeft",
        ),
    )

    obj_name = models.TextField(
        "object",
        null=True,
        blank=True,
        config=Config(
            doc_short="Object waar de log betrekking op heeft. Bijvoorbeeld een datatabel of bestand",
        ),
    )

    record_id = models.JSONField(
        "record id",
        null=True,
        blank=True,
        config=Config(
            doc_short="Id van het record waar de log betrekking op heeft",
        ),
    )

    fields = models.ArrayField(models.TextField(), null=True, blank=True)

    msg_code = models.ForeignKey(
        enums.EnumMessageCode,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="meldingscode",
        config=Config(
            doc_short="Code van de melding",
        ),
    )

    data = models.JSONField(
        "data",
        null=True,
        blank=True,
        config=Config(
            doc_short="Data van de log, wordt gebruikt in het template",
        ),
    )

    class Meta:
        db_table = "workflow_data_log"
        verbose_name = "workflow data log"
        verbose_name_plural = "workflow data logs"

    class TableDescription:
        section = section_task
        order = 5
        description = "Log van de workflow"

    def __str__(self):
        return f"{self.dt} - {self.dt} - {self.message}"
