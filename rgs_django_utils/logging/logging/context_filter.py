import logging

from .log_context import get_extra_info, get_run, get_task_info


class LogContextFilter(logging.Filter):
    def filter(self, record):
        setattr(record, "run", get_run())
        task_info = get_task_info()
        setattr(record, "task_name", task_info.get("task_name") if task_info else "")
        extra_info_record = getattr(record, "extra_info", {})
        extra_info_context = get_extra_info()
        if extra_info_context:
            setattr(record, "extra_info", {**extra_info_context, **extra_info_record})

        return True
