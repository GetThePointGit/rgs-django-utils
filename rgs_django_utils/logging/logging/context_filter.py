import logging

from .log_context import get_extra_info, get_run, get_task_info


class LogContextFilter(logging.Filter):
    """Attach run / task / extra-info context to every ``LogRecord``.

    Install this filter on handlers that need the rgs run/task columns
    available on the record (for instance :class:`PostgresHandler`).
    Extra info set per-record via ``extra={...}`` is merged with the
    context-level extra info, with per-record values winning.
    """

    def filter(self, record):
        """Augment *record* with ``run``, ``task_name`` and merged ``extra_info``."""
        setattr(record, "run", get_run())
        task_info = get_task_info()
        setattr(record, "task_name", task_info.get("task_name") if task_info else "")
        extra_info_record = getattr(record, "extra_info", {})
        extra_info_context = get_extra_info()
        if extra_info_context:
            setattr(record, "extra_info", {**extra_info_context, **extra_info_record})

        return True
