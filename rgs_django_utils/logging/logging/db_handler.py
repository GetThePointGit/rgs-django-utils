import json
import logging

from django.db import OperationalError, connections, transaction

from .log_context import get_run

log = logging.getLogger(__name__)


class PostgresHandler(logging.Handler):
    """Logging handler that writes records into a Postgres ``log`` table.

    Requires a Django database alias ``"logging"`` pointing at the target
    database and an existing schema with ``log_run`` + ``log`` tables.
    Must be paired with :class:`~rgs_django_utils.logging.logging.LogContextFilter`
    so every record carries the run/task/extra-info attributes.

    Notes
    -----
    * Records under a logger whose name starts with ``"data."`` are
      marked ``is_data_log = True`` — :func:`finish_task` uses this to
      separate program-level from data-level severity.
    * A run is flagged ``success = False`` as soon as any ``ERROR``-level
      or higher record is written against it.
    * Errors during the emit path are printed rather than raised so the
      logging layer cannot crash the caller.

    Examples
    --------
    Minimal ``logging.dictConfig`` wiring (see project's settings.py for
    a real example)::

        LOGGING = {
            "version": 1,
            "filters": {
                "context": {
                    "()": "rgs_django_utils.logging.logging.LogContextFilter",
                },
            },
            "handlers": {
                "postgres": {
                    "level": "DEBUG",
                    "class": "rgs_django_utils.logging.logging.PostgresHandler",
                    "filters": ["context"],
                },
            },
            "loggers": {
                "": {"handlers": ["postgres"], "level": "DEBUG"},
            },
        }

    Runtime pattern::

        set_run("example_run")
        with TaskContext("step-1"):
            log.info("starting")
            do_work()
        with TaskContext("step-2"):
            set_extra_info({"run_for": "test"})
            log.error("something broke", extra={"code": 12})
        finish_run()
    """

    def __init__(self):
        super().__init__()
        self.run = None
        self.max_level = 0

        self.last_log_message = None

    def emit(self, record: logging.LogRecord):
        """Insert *record* into the ``log`` table; flip the run to unsuccessful on ``ERROR``+."""
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
        """Finalise the active run and flush the ``logging`` DB connection."""
        run = get_run()

        if run is not None:
            run.finish()

        try:
            if not transaction.get_autocommit(using="logging"):
                transaction.commit(using="logging")
        except OperationalError as e:
            print("Fout bij het afsluiten van de database connectie", e)

        super().close()
