import logging
from datetime import datetime

import rgs_django_utils.logging as custom_logging
from celery import shared_task, states
from celery.worker.control import revoke
from core.models.user import User
from django.utils import timezone
from django_celery_results.models import TaskResult  # noqa: E402  # noqa: E402
from rgs_django_utils.models import EnumTaskStatus, Task, Workflow  # noqa: E402  # noqa: E402
from thissite import celery_app

log = logging.getLogger(__name__)


@shared_task
def queue_workflow_methods(
    user_id: int,
    workflow_id: int,
    step_id: str,
    run_sync: bool = False,
):
    """Queue workflow methods on the Celery worker.

    Args:
        user_id (int): user that queued the workflow tasks
        workflow_id (int): workflow ID
        step_id (str): step of which to execute the shared method
        run_sync (bool): To run the task synchronous, for development and debugging only. Defaults to False. Tasks that immediately follow this task are queued on the worker.
    """
    _run_workflow_methods(
        user_id,
        workflow_id,
        step_id,
        run_sync,
    )


def _run_workflow_methods(
    user_id: int,
    workflow_id: int,
    step_id: str,
    run_sync: bool = False,
):
    """Run shared workflow methods.
    This is used to run (shared) methods in the background.

    Errors are caught and logged in task.logs.

    If the shared method logs errors then the task status is set to failed.
    If the shared method logs warnings and no errors then the task status is set to completed with warnings.
    If the shared method logs no errors and no warnings then the task status is set to completed.

    If in the configuration of the shared method the requires_user_input of the next step is set to False, the next step is run in the same service worker task.
    Unless run_sync is set to True, in which case the next step is queued on the worker.

    TODO: This method is called by the Celery worker. As such it must not raise exceptions.
    Only problem is where to log if the workflow or task is not found.

    Args:
        user_id (int): user that queued the workflow tasks
        workflow_id (int): workflow ID
        step_id (str): step of which to execute the shared method
        run_sync (bool): To run the task synchronous, for development and debugging only. Defaults to False. Tasks that immediately follow this task are queued on the worker.

    Raises:
        Workflow.DoesNotExist: If the user is not found.
        Task.DoesNotExist: If the task is not found.
    """
    workflow = Workflow.objects.get(pk=workflow_id)
    task: Task = workflow.tasks.get(step_id=step_id)
    task.status_id = EnumTaskStatus.QUEUED
    task.activate(user_id=user_id)
    task.save()
    logging.info(msg=f"Running workflow method for task {task.id} in workflow {workflow.id} for user {user_id}.")
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        task.status_id = EnumTaskStatus.FAILED
        task.logs.create(
            level=custom_logging.levels.ERROR,
            message="Onverwachte fout: Kon opgegeven gebruiker niet vinden.",
        )
        task.save()
        return
    workflow_class = workflow.workflow_class
    try:
        shared_method = workflow_class.get_shared_method_for_step(step_id)

        task.logs.create(
            level=custom_logging.levels.INFO,
            message="De taak wordt gestart.",
        )
        task.status_id = EnumTaskStatus.IN_PROGRESS
        task.started = timezone.now()
        task.save()

        shared_method.method(self=workflow_class, user_id=user.id, task=task)

    except Exception as e:
        log.exception(
            f"Unexpected error while running workflow method for task {task.id} in workflow {workflow.id} for user {user_id}."
        )
        task.status_id = EnumTaskStatus.FAILED
        task.finished = timezone.now()
        task.logs.create(
            level=custom_logging.levels.ERROR,
            message=f"Onverwachte fout: {str(e)}",
        )
        task.save()
        return
    else:
        if task.logs.filter(level__gte=custom_logging.levels.ERROR).exists():
            task.status_id = EnumTaskStatus.FAILED
            task.finished = timezone.now()
            task.logs.create(
                level=custom_logging.levels.ERROR,
                message="De taak is mislukt.",
            )
            task.save()
            return
        elif task.logs.filter(level__gte=custom_logging.levels.WARNING).exists():
            task.status_id = EnumTaskStatus.COMPLETED_WITH_WARNINGS
            task.finished = timezone.now()
            task.logs.create(
                level=custom_logging.levels.WARNING,
                message="De taak is geslaagd, maar wel met waarschuwingen.",
            )
            task.save()
        else:
            task.status_id = EnumTaskStatus.COMPLETED
            task.finished = timezone.now()
            task.logs.create(
                level=custom_logging.levels.INFO,
                message="De taak is geslaagd.",
            )
            task.save()

    next_step_id = workflow_class.get_next_step(task.step_id)
    if next_step_id is None:
        # If there is no next step, assume the workflow is completed.
        return

    # If there is a next step, set the status of the next task.
    try:
        next_task: Task = workflow.tasks.get(step_id=next_step_id)
        next_task.activate(user_id=user_id)
        next_shared_method = workflow_class.get_shared_method_for_step(next_step_id)
    except Exception:
        task.status_id = EnumTaskStatus.FAILED
        task.logs.create(
            level=custom_logging.levels.ERROR,
            message="Onverwachte fout: Kon volgende taak niet vinden.",
        )
        task.save()
    except Exception as e:
        next_task.status_id = EnumTaskStatus.FAILED
        next_task.logs.create(
            level=custom_logging.levels.ERROR,
            message=f"Onverwachte fout: {str(e)}",
        )
        next_task.save()
        return
    if next_shared_method.requires_user_input:
        # If the next shared method requires user input, set the task status to wait for user input.
        next_task.status_id = EnumTaskStatus.WAIT_FOR_USER_INPUT
        next_task.save()
        return
    # TODO: Do we always want to run the next step asynchronously?
    # If not, we should add a configuration option to the shared method (like requires_user_input).
    if run_sync:
        # the task was run synchronously, so the next task is queued for the service worker.
        next_task.status_id = EnumTaskStatus.QUEUED
        next_task.last_modified_by_id = user_id
        next_task.last_modified_at = datetime.now()
        next_task.save()
        queue_workflow_methods.delay_on_commit(
            user_id=user_id,
            workflow_id=workflow_id,
            step_id=next_step_id,
            run_sync=False,
        )
    else:
        # the task is run asynchronously, so continue to execute the next task on the service worker.
        queue_workflow_methods(
            user_id=user_id,
            workflow_id=workflow_id,
            step_id=next_step_id,
            run_sync=False,
        )


def sync_running_workflow_tasks():
    """Syncs the status of running tasks in Django with the status of the tasks on the worker.
    This task is scheduled to run every 15 minutes.

    For running tasks in Django, the status is updated based on the status of the task on the worker.
    If the same task is found on the worker, but with a more recent creation date, the task in Django is cancelled.
    """

    running_tasks_in_django = Task.objects.filter(status_id=EnumTaskStatus.IN_PROGRESS).values_list(
        "last_modified_by_id",
        "workflow_id",
        "step_id",
    )

    for task in running_tasks_in_django:
        task: Task
        try:
            celery_task = TaskResult.objects.get(
                args=f"({task[0]}, {task[1]}, {task[2]})",
            )
        except TaskResult.DoesNotExist:
            task.status = EnumTaskStatus.CANCELLED
            task.logs.create(
                user_id=task.last_modified_by_id,
                log="De taak is niet gevonden op de worker. Mogelijk is de taak geannuleerd door een herstart of onverwachte fout.",
            )
            task.save()
            continue
        except TaskResult.MultipleObjectsReturned:
            celery_tasks = TaskResult.objects.filter(args=f"({task[0]}, {task[1]}, {task[2]})").order_by(
                "date_created"
            )
            celery_task = celery_tasks[-1]
            for task in celery_tasks.exclude(pk=celery_task.pk).filter(status=states.STARTED):
                revoke(task.id, terminate=True)  # TODO: Does Django atomic rollback work with revoke?
                task.status = EnumTaskStatus.CANCELLED
                task.logs.create(
                    user_id=task.last_modified_by_id,
                    log="Deze taak is geannuleerd omdat er eenzelfde taak op de worker is gevonden, maar met een aanmaakdatum die meer recent is.",
                )
                task.save()

        if celery_task.status != states.STARTED:
            task.status = _map_celery_task_result_to_task_status(celery_task.status)
            task.logs.create(
                user_id=task.last_modified_by_id,
                log=f"De status van de taak op de worker is {celery_task.status}. Mogelijk is de taak mislukt of geannuleerd door een herstart of onverwachte fout.",
            )
            task.save()


def _map_celery_task_result_to_task_status(status: states):
    if status == states.STARTED:
        return EnumTaskStatus.IN_PROGRESS
    elif status == states.SUCCESS:
        return EnumTaskStatus.COMPLETED
    elif status == states.FAILURE:
        return EnumTaskStatus.FAILED
    elif status == states.REVOKED:
        return EnumTaskStatus.CANCELLED
    else:
        return EnumTaskStatus.NOT_STARTED


class WorkflowServiceQueue:
    """Service to queue workflow methods. This is used to queue methods that are executed in the background."""

    _celeryService = None
    _mockService = None

    @classmethod
    def get_instance(cls) -> "WorkflowServiceQueue":
        """Get the instance of the workflow service queue.

        Returns:
            WorkfowServiceQueue: Instance of the workflow service queue.
        """
        from django.conf import settings

        if settings.WORKFLOW_SERVICE["queue"] == "celery":
            if cls._celeryService is None:
                cls._celeryService = CeleryWorkflowServiceQueue()
            return cls._celeryService
        elif settings.WORKFLOW_SERVICE["queue"] == "mock":
            if cls._mockService is None:
                cls._mockService = WorkflowServiceQueueMock()
            return cls._mockService
        else:
            raise ValueError("Invalid workflow service queue")

    def queue_workflow_method(
        self,
        user_id: int,
        workflow_id: int,
        step_id: str,
        run_sync: bool = False,
    ):
        """Queue a workflow method to be executed in the background.

        Errors are caught and logged in task.logs.

        If the shared method logs errors then the task status is set to failed.
        If the shared method logs warnings and no errors then the task status is set to completed with warnings.
        If the shared method logs no errors and no warnings then the task status is set to completed.

        If in the configuration of the shared method the requires_user_input of the next step is set to False, the next step is run in the same service worker task.
        Unless run_sync is set to True, in which case the next step is queued on the worker.

        Args:
            user_id (int): user that queued the workflow tasks
            workflow_id (int): workflow ID
            step_id (str): step of which to execute the shared method
            run_sync (bool): To run the task synchronous, for development and debugging only. Defaults to False. Tasks that immediately follow this task are queued on the worker.
        """
        raise NotImplementedError()


class CeleryWorkflowServiceQueue(WorkflowServiceQueue):
    """Service to queue workflow methods using Celery.

    Args:
        WorkfowServiceQueueBase (_type_): Base class for the workflow service queue.
    """

    def queue_workflow_method(
        self,
        user_id: int,
        workflow_id: int,
        step_id: str,
        run_sync: bool = False,
    ):
        """Queue a workflow method to be executed in the background.

        Errors are caught and logged in task.logs.

        If the shared method logs errors then the task status is set to failed.
        If the shared method logs warnings and no errors then the task status is set to completed with warnings.
        If the shared method logs no errors and no warnings then the task status is set to completed.

        If in the configuration of the shared method the requires_user_input of the next step is set to False, the next step is run in the same service worker task.
        Unless run_sync is set to True, in which case the next step is queued on the worker.

        Args:
            user_id (int): user that queued the workflow tasks
            workflow_id (int): workflow ID
            step_id (str): step of which to execute the shared method
            run_sync (bool): To run the task synchronous, for development and debugging only. Defaults to False. Tasks that immediately follow this task are queued on the worker.
        """
        # Use delay_on_commit to ensure that the task is only executed after the commit.
        # Otherwise instances created in the workflow will not be available and the task will fail.
        # https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html#django-first-steps

        if not run_sync:
            try:
                queue_workflow_methods.delay_on_commit(user_id, workflow_id, step_id, run_sync)
            except Exception as e:
                task = Task.objects.get(workflow_id=workflow_id, step_id=step_id)
                task.logs.create(
                    level=custom_logging.levels.ERROR,
                    message="Onverwachte fout bij het in de wachtrij zetten van de taak.",
                )
                log.exception(
                    f"Unexpected error while queueing task {task.id} in workflow {workflow_id} for user {user_id}."
                )
                task.status_id = EnumTaskStatus.FAILED
                task.save()
        else:
            queue_workflow_methods(user_id, workflow_id, step_id, run_sync)


class WorkflowServiceQueueMock(WorkflowServiceQueue):
    """Mock service to queue workflow methods.

    Args:
        WorkfowServiceQueueBase (_type_): Base class for the workflow service queue.
    """

    def __init__(self):
        self._queue: list[
            list[
                tuple[
                    int,
                    int,
                ]
            ]
        ] = []

    def queue_workflow_method(
        self,
        user_id: int,
        workflow_id: int,
        step_id: str,
        run_sync: bool = False,
    ):
        """Queue a workflow method to be executed in the background.

        Errors are caught and logged in task.logs.

        If the shared method logs errors then the task status is set to failed.
        If the shared method logs warnings and no errors then the task status is set to completed with warnings.
        If the shared method logs no errors and no warnings then the task status is set to completed.

        If in the configuration of the shared method the requires_user_input of the next step is set to False, the next step is run in the same service worker task.
        Unless run_sync is set to True, in which case the next step is queued on the worker.

        Args:
            user_id (int): user that queued the workflow tasks
            workflow_id (int): workflow ID
            step_id (str): step of which to execute the shared method
            run_sync (bool): To run the task synchronous, for development and debugging only. Defaults to False. Tasks that immediately follow this task are queued on the worker.
        """
        if run_sync:
            _run_workflow_methods(user_id, workflow_id, step_id, run_sync)
        else:
            self._queue.append((user_id, workflow_id, step_id))

    @property
    def queue(self):
        return self._queue

    def process_queue(self):
        for params in self._queue:
            _run_workflow_methods(*params)
