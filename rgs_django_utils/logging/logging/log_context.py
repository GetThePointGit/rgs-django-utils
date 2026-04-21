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
    """Start (or continue) a ``LogRun`` context in the current async-safe scope.

    Parameters
    ----------
    name : str
        Name of the run. If a run with the same name is already active
        the existing one is reused; a different name first finalises the
        previous run.

    Returns
    -------
    LogRun, bool
        ``(run, created)`` — the active ``LogRun`` instance and a boolean
        indicating whether a new row was created in this call.

    Notes
    -----
    The concrete implementation depends on the consumer app's
    ``LogRun`` model and is currently stubbed out — see the commented
    block below for the intended behaviour.
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
    """Context manager that opens a task within the currently active run.

    On ``__enter__`` calls :func:`set_task`; on ``__exit__`` calls
    :func:`finish_task`, which emits the timing/summary log entry for the
    task if ``log_timing`` is on.

    Parameters
    ----------
    name : str
        Task name — used as the log-field value and for matching against
        an existing task context.
    log_timing : bool, optional
        Emit a timing summary to ``task.performance`` on exit. Default
        is ``True``.

    Examples
    --------
    >>> with TaskContext("clean_duplicate_history"):   # doctest: +SKIP
    ...     do_the_work()
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
    """Context manager that brackets code with :func:`set_run` / :func:`finish_run`.

    Parameters
    ----------
    name : str
        Run name passed straight to :func:`set_run`.

    Examples
    --------
    >>> with RunContext("nightly-import"):        # doctest: +SKIP
    ...     with TaskContext("load-measurements"):
    ...         import_measurements()
    """

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
    """Wall-clock + CPU-time timer for an inner work unit.

    Unlike :class:`TaskContext`, a sub-timer does not interact with the
    run/task context stack — it just logs duration/process_duration to
    ``task.performance.sub`` when it finishes. Typically used inside a
    :class:`TaskContext` to measure a nested block.

    Parameters
    ----------
    name : str
        Sub-timer label emitted with the timing log line. Falsy values
        suppress the "started" log line but still emit the "finished"
        summary.
    """

    def __init__(self, name):
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


def get_run() -> typing.Union["LogRun", None]:  # noqa: F821 — LogRun is provided by the consumer app (e.g. spoc_hhnk.models), not defined here
    """Return the currently active ``LogRun`` instance, or ``None`` when none is active."""
    return ctx_run.get()


def finish_run():
    """Close the active ``LogRun`` by calling ``run.finish()`` and clearing the context."""
    run = get_run()
    if run is not None:
        task_console_info(f"Run {run.name} finished")
        run.finish()
        ctx_run.set(None)


def set_task(name: str, log_timing: bool = True):
    """Start (or continue) a task context in the current scope.

    Parameters
    ----------
    name : str
        Task name. If a different task is currently active it is finalised
        first; re-using the same name is a no-op on the existing context.
    log_timing : bool, optional
        Record wall-clock + CPU-time for this task and emit a timing
        summary on finish. Default is ``True``.

    Returns
    -------
    dict, bool
        ``(task_info, created)`` — the active task info dict and a boolean
        indicating whether it was created in this call.
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
    """Return the active task info dict, or ``None`` when no task is active.

    Dict keys: ``task_name``, ``start_time``, ``start_process_time``,
    ``log_timing``, ``max_level``.
    """
    return ctx_task_info.get()


def get_count_info() -> typing.Union[dict, None]:
    """Return the ``{name: count}`` mapping for the active task, or ``None``."""
    return ctx_counts.get()


def finish_task():
    """Finalise the active task — emit the timing summary when ``log_timing`` is set.

    When a ``LogRun`` is active, the final summary level is lifted to at
    least ``WARNING`` if any child log entry (program or data) reached
    that level, so the overview log surfaces failing tasks even when the
    task itself returned successfully.
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
    """Merge *info* into the task's ``extra_info`` context dict.

    Values passed later overwrite earlier values for the same key.

    Parameters
    ----------
    info : dict
        Additional fields to make available to every subsequent log call
        in the current scope.

    Returns
    -------
    dict
        The merged extra-info dict.
    """
    extra_info = get_extra_info()
    if extra_info is None:
        extra_info = info
    else:
        extra_info.update(info)

    ctx_extra_info.set(extra_info)
    return extra_info


def get_extra_info() -> typing.Union[dict, None]:
    """Return the current ``extra_info`` dict, or ``None`` when unset."""
    return ctx_extra_info.get()


def clear_extra_info():
    """Drop the ``extra_info`` context dict back to ``None``."""
    ctx_extra_info.set(None)


def log_counter(name: str, number: int = 1):
    """Increment the named counter in the active task's counts dict.

    Counters accumulated during a task are emitted as part of
    :func:`finish_task`'s summary line, which is handy for "imported N
    rows / skipped M rows" style reports.

    Parameters
    ----------
    name : str
        Counter key.
    number : int, optional
        Increment (may be negative). Default is ``1``.
    """
    counts = ctx_counts.get()
    if counts is None:
        counts = {}
    if name in counts:
        counts[name] += number
    else:
        counts[name] = number

    ctx_counts.set(counts)
