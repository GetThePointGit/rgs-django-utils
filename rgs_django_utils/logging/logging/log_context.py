import logging
import time
import typing
from contextvars import ContextVar

from django.db.models import Max

from .loggers import task_console_info

# if typing.TYPE_CHECKING:
#     from spoc_hhnk.models import LogRun

# this should be thread safe
ctx_run = ContextVar("run", default=None)
ctx_task_info = ContextVar("task", default=None)
ctx_extra_info = ContextVar("extra_info", default=None)
ctx_counts = ContextVar("counts", default=None)

task_performance_logger = logging.getLogger("task.performance")
sub_task_performance_logger = logging.getLogger("task.performance.sub")


def set_run(name: str):
    """
    set log run for logging. Checks if name has changed, otherwise returns existing logRun
    :param name: name of the run
    :return: LogRun, bool: LogRun object, True if new LogRun object was created
    """
    pass


#     from spoc_hhnk.models import LogRun  # noqa: C0415, import here to prevent circular imports
#
#     run: typing.Union[LogRun, None] = ctx_run.get()
#
#     if run and run.name != name:
#         finish_run()
#         run = None
#
#     if run is None:
#         task_console_info(f"Run {name} started")
#         run = LogRun.objects.using("logging").create(name=name)
#         ctx_run.set(run)
#         return run, True
#
#     return run, False


class TaskContext:
    """Open a new task within a run.

    example use:
    with TaskContext("clean_duplicate_history"):
        call a command...
    """

    def __init__(self, name: str, log_timing: bool = True):
        self.name = name
        self.log_timing = log_timing

    def __enter__(self):
        set_task(self.name, self.log_timing)

    def __exit__(self, *args):
        self.finish()

    def finish(self):
        finish_task()
        self.name = None


class RunContext:
    def __init__(self, name: str):
        self.name = name

    def __enter__(self):
        set_run(self.name)

    def __exit__(self, *args):
        self.finish()

    def finish(self):
        finish_run()
        self.name = None


class SubTimer:
    def __init__(self, name):
        """Start a timer
        use .finish() to stop the timer.
        """
        self.name = name
        self.start = time.time()
        self.process_duration = time.process_time()

        if name:
            task_console_info(f"Sub {name} started")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.finish()

    def finish(self):
        sub_task_performance_logger.info(
            f"Sub {self.name}: duration: {time.time() - self.start:.3f}, process_duration: {time.process_time() - self.process_duration:.3f}"
        )


def get_run() -> typing.Union["LogRun", None]:
    """get_run
    get log run if exists (instance of LogRun - django model)
    """
    return ctx_run.get()


def finish_run():
    """finish_run
    finish log run by adding end time and set run context to None
    """
    run = get_run()
    if run is not None:
        task_console_info(f"Run {run.name} finished")
        run.finish()
        ctx_run.set(None)


def set_task(name: str, log_timing: bool = True):
    """
    set task info for logging. Checks if name has changed, otherwise returns existing task info
    :param name: name of the task
    :param log_timing: log timing of the task to 'task_performance' logger
    :return: dict, bool: task info dict, True if new task info was created
    """

    task_info = get_task_info()
    if task_info is not None and task_info.get("task_name") != name:
        # finish previous task
        finish_task()
        task_info = None

    if task_info is None:
        task_info = {
            "task_name": name,
            "start_time": time.time(),
            "start_process_time": time.process_time(),
            "log_timing": log_timing,
            "max_level": 0,
        }

        ctx_task_info.set(task_info)
        ctx_counts.set({})
        task_console_info(f"Task {name} started")
        return task_info, True
    else:
        return task_info, False


def get_task_info() -> typing.Union[dict, None]:
    """
    get task info
    :return: dict: task info dict, with task_name, start_time, start_process_time, log_timing
    """
    return ctx_task_info.get()


def get_count_info() -> typing.Union[dict, None]:
    """
    get count info
    :return: dict: with names and counts
    """
    return ctx_counts.get()


def finish_task():
    """finish_task
    finish task and log timing if log_timing is set
    """
    task_info = get_task_info()
    if task_info and task_info.get("log_timing"):
        task_console_info(f"Finished task {task_info['task_name']}")
        duration = time.time() - task_info["start_time"]
        process_duration = time.process_time() - task_info["start_process_time"]
        task_info["duration"] = duration
        task_info["process_duration"] = process_duration

        # get info about the task
        level = logging.INFO
        msg = f"Task {task_info['task_name']} finished"

        run = get_run()
        if run:
            prog_level = (
                run.logs.filter(task_name=task_info["task_name"], is_data_log=False)
                .aggregate(max_level=Max("level"))
                .get("max_level", 0)
            )

            if prog_level is None:
                prog_level = 0

            if prog_level >= logging.WARNING:
                msg += f" programma {logging.getLevelName(prog_level)}"

            data_level = (
                run.logs.filter(task_name=task_info["task_name"], is_data_log=True)
                .aggregate(max_level=Max("level"))
                .get("max_level", 0)
            )

            if data_level is None:
                data_level = 0

            if data_level >= logging.WARNING:
                msg += f" data {logging.getLevelName(data_level)}"

            level = max(prog_level, data_level - 10, logging.INFO)

        task_performance_logger.log(
            level, f"{msg}: duration: {duration:.2f}, process_duration: {process_duration:.2f}."
        )
        counts = ctx_counts.get()
        if counts:
            lines = [f"* Task summary {task_info['task_name']}"]
            for name, count in counts.items():
                lines.append(f"* - {name}: {count}")
            task_performance_logger.info("\n".join(lines))
            ctx_counts.set(None)

    ctx_task_info.set(None)


def set_extra_info(info: dict):
    """
    set extra info for logging
    :param info: dict: extra info to add to the log
    :return: dict: extra info dict (merged with existing extra info)
    """
    extra_info = get_extra_info()
    if extra_info is None:
        extra_info = info
    else:
        extra_info.update(info)

    ctx_extra_info.set(extra_info)
    return extra_info


def get_extra_info() -> typing.Union[dict, None]:
    """
    get extra info
    :return: dict: extra info dict
    """
    return ctx_extra_info.get()


def clear_extra_info():
    """clear_extra_info
    clear extra info
    """
    ctx_extra_info.set(None)


def log_counter(name: str, number: int = 1):
    """
    count a certain event, can be logged in a summary when a task is finished
    :param name: str: name of the event
    :param number: int: number to add to the counter
    """
    counts = ctx_counts.get()
    if counts is None:
        counts = {}
    if name in counts:
        counts[name] += number
    else:
        counts[name] = number

    ctx_counts.set(counts)
