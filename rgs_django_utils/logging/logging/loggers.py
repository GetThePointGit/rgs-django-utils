import logging

"""
task_console_info is a logger for logging of tasks to the console only.
replacement for the stdout.write statements in the commands
"""
task_to_console = logging.getLogger("task_console_info")


def task_console_info(message, *args, **kwargs):
    """Task_console_info is a logger for logging of tasks to the console only.

    Replacement for the stdout.write statements in the commands
    """
    task_to_console.info(message, *args, **kwargs)


def get_data_logger(module_name):
    """get_data_logger
    data logger is a logger specially for logs about data.
    Logging (of errors, etc.) will be marked 'for data' in the db logging and
    logs of log levels will be counted separately.
    """
    return logging.getLogger("data." + module_name)
