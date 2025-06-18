import json
import logging

from django.db import OperationalError, connections, transaction

from .log_context import get_run

log = logging.getLogger(__name__)


class PostgresHandler(logging.Handler):
    """Custom logging handler to log to a PostgreSQL database
    With additional support of LogRun, task context and extra info

    Example configuration:
    ```
    import logging
    from spoc_hhnk.utils.logging.db_handler import PostgresHandler

    # load config from dictionary
    logging.dictConfig({
        'version': 1,
        'filters': {
            'context': {
                '()': 'spoc_hhnk.utils.logging.LogContextFilter'
        'handlers': {
            'postgres': {
                'level': 'DEBUG',
                'class': 'spoc_hhnk.utils.logging.PostgresHandler',
                'filters': ['context'],
            },
        },
        'loggers': {
            '': {
                'handlers': ['postgres'],
                'level': 'DEBUG',
            },
        },
    })

    ```

    Example usage:
    ```
    import logging
    log = logging.getLogger('spoc_hhnk.test')

    # on start of run, set a run so all logging will be grouped by this run
    set_run('example_run')

    # set task info for logging
    set_task('example task step 1')

    log.info('test_info')
    run_task_step_1()

    # second task
    set_task('example task step 2')
    # set extra info for logging
    set_extra_info({'run_for': 'test'})
    log.error('test_error', extra={'code':12})
    run_task_step_2()
    finish_task()

    # finish run
    finish_run()
    ```
    for this example there will be a log_run like:

    | id | name        | start_time          | end_time            | success |
    |----|-------------|---------------------|---------------------|---------|
    | 1  | example_run | 2021-08-17 12:00:00 | 2021-08-17 12:03:00 | True    |

    and logs like:

    | id | run_id | task_name           | level | name             | code | dt                  | message                                                            | filename       | line_nr | extra              |
    |----|--------|---------------------|-------|------------------|------|---------------------|--------------------------------------------------------------------|----------------|---------|--------------------|
    | 1  | 1      | example task step 1 | 20    | spoc_hhnk.test   |      | 2021-08-17 12:00:00 | test_info                                                          | example.py     | 10      | {}                 |
    | 2  | 1      | example task step 1 | 20    | task.performance |      | 2021-08-17 12:01:00 | example task step 1: duration: 60.00, process_duration: 2.00       | log_context.py | 109     | {}                 |
    | 3  | 1      | example task step 2 | 40    | spoc_hhnk.test   | 12   | 2021-08-17 12:01:01 | test_error                                                         | exmaple.py     | 20      | {"run_for": "test} |
    | 4  | 1      | example task step 2 | 20    | task.performance |      | 2021-08-17 12:02:00 | Task example task step 2: duration: 59.00, process_duration: 3.00  | log_context.py | 109     | {"run_for": "test} |

    """

    def __init__(self):
        super().__init__()
        self.run = None
        self.max_level = 0

        self.last_log_message = None

    def emit(self, record: logging.LogRecord):
        run = getattr(record, "run", None)

        try:
            if run != self.run:
                self.max_level = 0
                self.run = run

            run_id = self.run.id if self.run else None
            task_name = getattr(record, "task_name", "")[:30]
            name = record.name[:30]
            level = record.levelno
            is_data_log = name.startswith("data.")
            code = getattr(record, "code", None)
            dt = record.created
            message = self.format(record)

            self.last_log_message = message

            filename = record.filename[:30]
            line_nr = record.lineno

            # Voorbeeld voor het omgaan met aangepaste eigenschappen
            # Je zou dit dynamisch kunnen maken afhankelijk van de gebruikssituatie
            extra_info = json.dumps(getattr(record, "extra_info", {}))

            if run is not None and level >= logging.ERROR and not run.success:
                run.success = False
                run.save()

            with connections["logging"].cursor() as cursor:
                cursor.execute(
                    "INSERT INTO log (run_id, task_name, level, name, is_data_log, code, dt, message, filename, line_nr, extra) VALUES (%s, %s, %s, %s, %s, %s, to_timestamp(%s), %s, %s, %s, %s)",
                    (run_id, task_name, level, name, is_data_log, code, dt, message, filename, line_nr, extra_info),
                )
        except Exception as e:
            print("Fout bij het loggen naar de database", e)
            self.handleError(record)

    def close(self):
        run = get_run()

        if run is not None:
            run.finish()

        try:
            if not transaction.get_autocommit(using="logging"):
                transaction.commit(using="logging")
        except OperationalError as e:
            print("Fout bij het afsluiten van de database connectie", e)

        super().close()
