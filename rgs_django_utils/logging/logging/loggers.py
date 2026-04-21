import logging

"""
task_console_info is a logger for logging of tasks to the console only.
replacement for the stdout.write statements in the commands
"""
task_to_console = logging.getLogger("task_console_info")


def task_console_info(message, *args, **kwargs):
    """Emit an ``INFO`` line to the ``task_console_info`` logger.

    Console-only replacement for ``self.stdout.write(...)`` calls inside
    Django management commands, so the command output is captured by the
    standard logging chain (and indirectly by :class:`PostgresHandler`).
    Arguments are forwarded verbatim to :meth:`logging.Logger.info`.
    """
    task_to_console.info(message, *args, **kwargs)


def get_data_logger(module_name):
    """Return a logger whose name is prefixed with ``data.``.

    Loggers under the ``data.`` namespace are singled out by
    :class:`PostgresHandler` (``is_data_log = True``) so that data-level
    severity can be reported separately from program-level severity in
    the run summary.

    Parameters
    ----------
    module_name : str
        Name of the module or subsystem producing the log records. The
        resulting logger is called ``data.<module_name>``.
    """
    return logging.getLogger("data." + module_name)
