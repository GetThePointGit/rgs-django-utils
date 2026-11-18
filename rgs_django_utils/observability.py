"""Observability-basis: logging-config, Sentry-init en Prometheus-koppeling.

Gedeeld door de backends (waterworks, urbanworks); elke Sentry- of loggingfix
landt zo op één plek. Rolverdeling:

- **Sentry** krijgt de uitzonderingen: onverwachte errors (met een ruisfilter)
  en gericht gesamplede traces. Achtergrondtaken volledig (laag volume, hoge
  waarde), web-requests met een laag referentiepercentage, health-checks nooit.
- **Prometheus** krijgt de tijdreeksen; deze module levert daarvoor de teller
  van WARNING/ERROR-logregels per module.
- **Python-logging** is de basis: per-module niveaus zijn via de
  ``LOG_LEVELS``-env instelbaar zonder redeploy, en het logniveau bepaalt via
  Sentry's LoggingIntegration wat een breadcrumb (INFO+) dan wel een event
  (ERROR) wordt.

App-specifieke keuzes zijn parameters van :func:`init_sentry`: de sample rates,
de Celery-integratie (``celery=True``) en de redactie van de Kuma push-URL
(``redact_kuma=True``). De Procrastinate-middleware
(:func:`sentry_task_middleware`) en :func:`silence_http_loggers` zijn losse
functies; de app hangt ze zelf op in de settings.

Zonder DSN doet :func:`init_sentry` niets, zodat lokale ontwikkeling geen quota
gebruikt en niet omvalt op een ontbrekende configuratie.

Deze module heeft ``prometheus-client`` nodig, en ``sentry-sdk`` zodra de SDK
echt wordt aangezet; beide zitten in de extra ``rgs-django-utils[observability]``.
"""

import logging
import sys
from urllib.parse import urlsplit

from prometheus_client import Counter

logger = logging.getLogger(__name__)

#: Teller van logregels op WARNING of hoger, per top-level module en niveau.
#: Bewust alleen het eerste segment van de loggernaam als label om de
#: cardinaliteit laag te houden (``core.tasks.imports`` telt als ``core``).
#: Eén naam voor alle apps, zodat de dashboards in rgs-deployments overal
#: werken (onderscheid via het job-label).
LOG_RECORDS_TOTAL = Counter(
    "wit_log_records_total",
    "Logregels op WARNING of hoger, per top-level module en niveau.",
    ["module", "level"],
)

#: Paden die nooit een Sentry-trace mogen opleveren.
HEALTH_PATHS = ("/livez/", "/readyz/", "/health/", "/metrics")

#: ``op``-waarde van de transacties die :func:`sentry_task_middleware` opent.
#: De traces_sampler herkent Procrastinate-taken hieraan; Procrastinate heeft
#: geen eigen Sentry-integratie die dat voor ons doet.
TASK_OP = "queue.task.procrastinate"

#: Management-commands die een handmatige, interactieve sessie zijn. Wat
#: daarin misgaat is geen applicatiefout en hoort niet in Sentry.
INTERACTIVE_COMMANDS = frozenset({"shell", "shell_plus", "dbshell"})

#: Sentry-environments die per definitie kortlevend zijn (PR-previews). Daar
#: maken we geen cron-monitors voor beat-taken aan: na het opruimen van de
#: omgeving blijven die anders eeuwig "missed check-in" melden.
EPHEMERAL_ENVIRONMENTS = frozenset({"preview"})

#: Vervangt de Kuma push-URL in Sentry-events en -breadcrumbs.
KUMA_PLACEHOLDER = "[kuma-heartbeat-url]"

#: Maximale nestdiepte waarop :func:`_redact` nog afdaalt.
MAX_REDACT_DIEPTE = 50

#: Vervangt een te diep genest deel, zodat daar geen onbekende tekst blijft staan.
TE_DIEP_PLACEHOLDER = "[te diep genest]"


class PrometheusLogCounterHandler(logging.Handler):
    """Logging-handler die WARNING+-regels telt in een Prometheus-counter.

    De handler schrijft niets weg; hij verhoogt alleen
    :data:`LOG_RECORDS_TOTAL`. Hang hem aan de root-logger zodat elke module
    meetelt, onafhankelijk van de geconfigureerde handlers.
    """

    def emit(self, record):
        """Tel het logrecord mee in de Prometheus-counter.

        Parameters
        ----------
        record : logging.LogRecord
            Het uit te tellen logrecord.
        """
        try:
            module = record.name.split(".", 1)[0] or "root"
            LOG_RECORDS_TOTAL.labels(module=module, level=record.levelname).inc()
        except Exception:  # noqa: BLE001 - logging mag nooit zelf falen
            self.handleError(record)


def parse_log_levels(spec):
    """Zet een ``LOG_LEVELS``-specificatie om naar een dict per logger.

    Parameters
    ----------
    spec : str or None
        Komma-gescheiden lijst van ``logger=NIVEAU``-paren, bv.
        ``"core.tasks.imports=DEBUG,django.db=WARNING"``. Lege of ontbrekende
        specificatie levert een lege dict.

    Returns
    -------
    dict of str
        Mapping van loggernaam naar (genormaliseerd, hoofdletter-)niveau.
        Ongeldige paren worden overgeslagen met een waarschuwing, zodat een
        typefout in de env nooit de app plat legt.
    """
    levels = {}
    if not spec:
        return levels
    valid = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        name, _, level = pair.partition("=")
        name, level = name.strip(), level.strip().upper()
        if not name or level not in valid:
            logger.warning("LOG_LEVELS: ongeldig paar %r overgeslagen", pair)
            continue
        levels[name] = level
    return levels


def build_logging_config(default_level="INFO", log_levels=None):
    """Bouw de ``LOGGING``-dict voor Django.

    Parameters
    ----------
    default_level : str, optional
        Niveau van de root-logger (default ``"INFO"``).
    log_levels : dict of str, optional
        Per-logger niveaus, doorgaans uit :func:`parse_log_levels`.

    Returns
    -------
    dict
        Een ``dictConfig``-compatibele logging-configuratie: alles naar stdout
        (k8s/``kubectl logs``), plus de Prometheus-logteller op de root-logger.
        ``disable_existing_loggers`` staat uit zodat libraries hun loggers
        houden, en zodat een eerder gezet niveau (zie
        :func:`silence_http_loggers`) blijft staan.
    """
    loggers = {name: {"level": level, "propagate": True} for name, level in (log_levels or {}).items()}
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "verbose",
            },
            "prometheus_counter": {
                "class": f"{__name__}.PrometheusLogCounterHandler",
                "level": "WARNING",
            },
        },
        "root": {
            "handlers": ["console", "prometheus_counter"],
            "level": default_level,
        },
        "loggers": loggers,
    }


def make_traces_sampler(web_rate=0.05, task_rate=1.0, health_paths=HEALTH_PATHS, unsampled_tasks=()):
    """Maak de Sentry ``traces_sampler`` met de afgesproken verdeling.

    Parameters
    ----------
    web_rate : float, optional
        Sample-rate voor web-/API-requests (referentiebeeld, default 0.05).
    task_rate : float, optional
        Sample-rate voor achtergrondtaken (default 1.0: laag volume, hoge
        waarde, zoals imports, exports en rekenwerk).
    health_paths : tuple of str, optional
        Padprefixen die nooit een trace opleveren (default
        :data:`HEALTH_PATHS`).
    unsampled_tasks : collection of str, optional
        Taaknamen die nooit een trace opleveren, bv. een heartbeat die elke
        minuut draait en alleen quota kost. Fouten erin gaan nog wel als event
        naar Sentry.

    Returns
    -------
    callable
        Functie ``sampling_context -> float`` voor ``sentry_sdk.init``.

    Notes
    -----
    Een achtergrondtaak wordt op twee manieren herkend: een Celery-taak aan
    ``celery_job`` in de sampling-context (gezet door Sentry's
    ``CeleryIntegration``), een Procrastinate-taak aan de transactie-``op``
    :data:`TASK_OP` (gezet door :func:`sentry_task_middleware`).

    Een door de frontend meegegeven sampling-beslissing (``parent_sampled``)
    wordt gerespecteerd voor web-requests, zodat een browser-trace niet
    halverwege de keten afbreekt. Een health-check wint daarvan.
    """
    health_paths = tuple(health_paths)
    unsampled_tasks = frozenset(unsampled_tasks)

    def traces_sampler(sampling_context):
        celery_job = sampling_context.get("celery_job")
        if celery_job is not None:
            taak = celery_job.get("task") if isinstance(celery_job, dict) else None
            return 0.0 if taak in unsampled_tasks else task_rate
        transaction_context = sampling_context.get("transaction_context") or {}
        if transaction_context.get("op") == TASK_OP:
            return 0.0 if transaction_context.get("name") in unsampled_tasks else task_rate
        scope = sampling_context.get("asgi_scope") or {}
        environ = sampling_context.get("wsgi_environ") or {}
        path = scope.get("path") or environ.get("PATH_INFO") or ""
        if any(path.startswith(p) for p in health_paths):
            return 0.0
        parent_sampled = sampling_context.get("parent_sampled")
        if parent_sampled is not None:
            return 1.0 if parent_sampled else 0.0
        return web_rate

    return traces_sampler


def redact_kuma_url(data):
    """Vervang de Kuma push-URL (met token) overal in ``data`` door een placeholder.

    Loopt recursief door dicts, lijsten en tuples en past strings op hun plek
    aan voor zover het containers zijn (dicts en lijsten worden in-place
    bijgewerkt, zodat een event dezelfde identiteit houdt). De setting
    ``KUMA_HEARTBEAT_URL`` wordt bij elke aanroep gelezen. Is die leeg of
    afwezig, dan gebeurt er niets.

    Parameters
    ----------
    data : object
        Een Sentry-event, -breadcrumb of een deel daarvan.

    Returns
    -------
    object
        Dezelfde structuur zonder de URL; een string wordt een nieuwe string.
    """
    from django.conf import settings

    url = getattr(settings, "KUMA_HEARTBEAT_URL", "")
    if not url or not isinstance(url, str):
        return data
    return _redact(data, _kuma_vormen(url), 0, set())


def _kuma_vormen(url):
    """Leid de te redigeren tekstvormen af uit de push-URL, langste eerst.

    Sentry's httpx-breadcrumb bewaart de URL zonder query, en foutteksten
    noemen soms alleen het pad of het kale token. Daarom: (a) de volledige URL,
    (b) de URL zonder query en fragment, (c) het token zelf (laatste
    niet-lege padsegment van b) mits minstens 8 tekens, zodat een kort segment
    nooit gewone tekst weghaalt.

    Parameters
    ----------
    url : str
        De geconfigureerde ``KUMA_HEARTBEAT_URL``.

    Returns
    -------
    tuple of str
        De vormen, langste eerst; gooit nooit een fout.
    """
    vormen = [url]
    try:
        basis = url.split("#", 1)[0].split("?", 1)[0]
        vormen.append(basis)
        # Alleen het pad: een push-URL zonder pad heeft geen token, en de
        # hostnaam is dan geen geheim dat we overal willen weghalen.
        segmenten = [deel for deel in urlsplit(basis).path.split("/") if deel]
        if segmenten and len(segmenten[-1]) >= 8:
            vormen.append(segmenten[-1])
    except Exception:  # noqa: BLE001 - een rare waarde mag het redigeren niet breken
        pass
    return tuple(sorted({v for v in vormen if v}, key=len, reverse=True))


def _redact(data, url, diepte=0, bezig=None):
    """Recursieve kern van :func:`redact_kuma_url`.

    Parameters
    ----------
    data : object
        Te bewerken waarde.
    url : tuple of str
        De te verwijderen tekstvormen, langste eerst (zie :func:`_kuma_vormen`).
    diepte : int, optional
        Huidige nestdiepte; boven :data:`MAX_REDACT_DIEPTE` wordt het deel
        vervangen door :data:`TE_DIEP_PLACEHOLDER`.
    bezig : set of int, optional
        ``id``'s van de containers waarin we nu zitten; een kringverwijzing
        wordt zo niet opnieuw doorlopen.

    Returns
    -------
    object
        De bewerkte waarde.
    """
    if bezig is None:
        bezig = set()
    if isinstance(data, str):
        for vorm in url:
            data = data.replace(vorm, KUMA_PLACEHOLDER)
        return data
    if not isinstance(data, dict | list | tuple):
        return data
    if diepte > MAX_REDACT_DIEPTE:
        return TE_DIEP_PLACEHOLDER
    if id(data) in bezig:
        return data
    bezig.add(id(data))
    try:
        if isinstance(data, dict):
            for key, value in data.items():
                data[key] = _redact(value, url, diepte + 1, bezig)
            return data
        if isinstance(data, list):
            for i, value in enumerate(data):
                data[i] = _redact(value, url, diepte + 1, bezig)
            return data
        return tuple(_redact(value, url, diepte + 1, bezig) for value in data)
    finally:
        bezig.discard(id(data))


def before_breadcrumb(crumb, hint):
    """Haal de Kuma push-URL uit een breadcrumb (httpx- en logging-breadcrumbs).

    Parameters
    ----------
    crumb : dict
        De kandidaat-breadcrumb.
    hint : dict
        Sentry-hint; wordt niet gebruikt.

    Returns
    -------
    dict
        De breadcrumb zonder push-URL.
    """
    return redact_kuma_url(crumb)


def silence_http_loggers():
    """Zet de ``httpx``- en ``httpcore``-logger op WARNING.

    ``httpx`` logt elk request met volledige URL op INFO. Een URL met een
    token erin (zoals de push-URL van de Kuma-heartbeat) mag niet elke minuut
    in logs en, via de LoggingIntegration, in Sentry-breadcrumbs belanden.
    Roep dit aan bij het laden van de settings, vóór de ``LOGGING``-config.
    """
    for naam in ("httpx", "httpcore"):
        logging.getLogger(naam).setLevel(logging.WARNING)


def before_send(event, hint):
    """Filter verwachte ruis uit de Sentry-events.

    Parameters
    ----------
    event : dict
        Het kandidaat-event.
    hint : dict
        Sentry-hint; bevat ``exc_info`` bij exception-events.

    Returns
    -------
    dict or None
        Het event, of ``None`` om het te laten vallen. Verwachte
        applicatiefouten (autorisatie, 404 en request-validatie) zijn geen
        software-defecten en gaan niet naar Sentry; ze blijven wel gewoon in
        de logs.
    """
    exc_info = hint.get("exc_info")
    if not exc_info:
        return event
    exc = exc_info[1]
    from django.http import Http404
    from ninja.errors import AuthenticationError, HttpError, ValidationError

    from rgs_django_utils.utils.authorization import UnauthorizedError

    expected = (
        Http404,
        PermissionError,
        UnauthorizedError,
        AuthenticationError,
        ValidationError,
    )
    if isinstance(exc, expected):
        return None
    if isinstance(exc, HttpError) and exc.status_code < 500:
        return None
    return event


def before_send_redacted(event, hint):
    """Als :func:`before_send`, maar eerst de Kuma push-URL uit het event.

    Parameters
    ----------
    event : dict
        Het kandidaat-event.
    hint : dict
        Sentry-hint; bevat ``exc_info`` bij exception-events.

    Returns
    -------
    dict or None
        Het geredigeerde event, of ``None`` om het te laten vallen.

    Notes
    -----
    Het redigeren gaat vóór het filter: ook exception-teksten en
    frame-variabelen kunnen de URL (met token) bevatten.
    """
    return before_send(redact_kuma_url(event), hint)


def is_interactive_shell(argv=None):
    """Draait dit proces als handmatige ``manage.py shell``-sessie?

    Parameters
    ----------
    argv : list of str, optional
        Commandoregel om te beoordelen; default ``sys.argv``.

    Returns
    -------
    bool
        ``True`` als het eerste niet-optie-argument na het script een commando
        uit :data:`INTERACTIVE_COMMANDS` is (``shell``, ``shell_plus``,
        ``dbshell``), ongeacht ``-c``/``--command``.

    Notes
    -----
    Een uitzondering in zo'n sessie (bv. een tikfout in een ad-hoc query via
    ``manage.py shell -c`` op een pod) gaat via ``sys.excepthook`` anders als
    event naar Sentry en vervuilt het issue-overzicht. Web-, worker- en overige
    management-processen worden hier níet als interactief gezien.

    Een losse optiewaarde vóór het subcommando (``-v 2 shell``) wordt voor het
    commando zelf aangezien en levert ``False``; Django zet opties na het
    subcommando.
    """
    args = sys.argv if argv is None else argv
    for arg in args[1:]:
        if arg.startswith("-"):
            continue
        return arg in INTERACTIVE_COMMANDS
    return False


def sentry_task_middleware(call_next, context, worker):
    """Procrastinate-middleware die elke taak als Sentry-transactie draait.

    Dit is het equivalent van Sentry's ``CeleryIntegration``: het geeft een
    taak een eigen transactie (herkenbaar aan :data:`TASK_OP`, waarmee de
    traces_sampler hem op ``task_rate`` zet) en zorgt dat een taak die klapt als
    event binnenkomt, met de taaknaam en het job-id erbij.

    Wordt nergens automatisch geregistreerd. Een app op Procrastinate hangt
    hem op met ``PROCRASTINATE_WORKER_DEFAULTS = {"task_middleware": [...]}``
    in de settings; de Django-integratie van Procrastinate geeft die door aan
    de worker.

    Parameters
    ----------
    call_next : callable
        Roept de volgende middleware of de taak zelf aan.
    context : procrastinate.JobContext
        Uitvoeringscontext van de lopende job.
    worker : procrastinate.worker.Worker
        De draaiende worker; hier niet gebruikt, maar onderdeel van de
        middleware-signatuur.

    Returns
    -------
    Any
        Wat de taak teruggeeft.

    Notes
    -----
    Zonder geïnitialiseerde SDK (lokale dev) is dit een gewone doorgeefluik:
    ``sentry_sdk`` is dan wel importeerbaar, maar alle scope-calls zijn no-ops.
    De uitzondering wordt opnieuw opgeworpen zodat Procrastinate zijn eigen
    retry-/foutafhandeling houdt.
    """
    import sentry_sdk

    job = getattr(context, "job", None)
    naam = getattr(job, "task_name", None) or "procrastinate.task"
    with sentry_sdk.isolation_scope() as scope:
        scope.set_tag("procrastinate.task", naam)
        if job is not None:
            scope.set_tag("procrastinate.queue", getattr(job, "queue", None))
            scope.set_context("procrastinate", {"job_id": getattr(job, "id", None), "task": naam})
        with sentry_sdk.start_transaction(op=TASK_OP, name=naam):
            try:
                return call_next()
            except Exception:
                sentry_sdk.capture_exception()
                raise


def init_sentry(
    dsn,
    environment,
    release,
    web_rate=0.05,
    task_rate=1.0,
    *,
    celery=False,
    redact_kuma=False,
    health_paths=HEALTH_PATHS,
    unsampled_tasks=(),
):
    """Zet de Sentry-SDK aan; no-op zonder DSN en in een handmatige shell.

    Parameters
    ----------
    dsn : str or None
        Sentry-DSN. Leeg of ``None`` betekent: SDK niet initialiseren, geen
        ruis of quota-gebruik in lokale dev.
    environment : str
        Sentry-environment (bv. ``prod``/``staging``/``dev``/``preview``).
    release : str
        Release-identificatie (image-tag/git-sha, terugval op het versienummer).
    web_rate, task_rate : float, optional
        Zie :func:`make_traces_sampler`.
    celery : bool, optional
        Voeg Sentry's ``CeleryIntegration`` toe (default ``False``). In een
        omgeving uit :data:`EPHEMERAL_ENVIRONMENTS` worden dan geen
        beat-cron-monitors aangemaakt. Een app op Procrastinate laat dit uit
        en hangt :func:`sentry_task_middleware` op.
    redact_kuma : bool, optional
        Haal de Kuma push-URL (setting ``KUMA_HEARTBEAT_URL``) uit elk event
        en elke breadcrumb (default ``False``).
    health_paths, unsampled_tasks : optional
        Zie :func:`make_traces_sampler`.

    Returns
    -------
    bool
        ``True`` als Sentry is geïnitialiseerd, anders ``False`` (geen DSN, of
        een interactieve ``manage.py shell``-sessie, zie
        :func:`is_interactive_shell`).
    """
    if not dsn or is_interactive_shell():
        return False
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    integrations = [DjangoIntegration()]
    if celery:
        from sentry_sdk.integrations.celery import CeleryIntegration

        integrations.append(CeleryIntegration(monitor_beat_tasks=environment not in EPHEMERAL_ENVIRONMENTS))
    # Expliciet, al is dit de default: INFO+ wordt breadcrumb (context bij een
    # error), pas ERROR wordt een event. Het per-module logniveau (LOG_LEVELS)
    # bepaalt dus ook wat Sentry ziet.
    integrations.append(LoggingIntegration(level=logging.INFO, event_level=logging.ERROR))

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        integrations=integrations,
        traces_sampler=make_traces_sampler(
            web_rate=web_rate,
            task_rate=task_rate,
            health_paths=health_paths,
            unsampled_tasks=unsampled_tasks,
        ),
        before_send=before_send_redacted if redact_kuma else before_send,
        before_breadcrumb=before_breadcrumb if redact_kuma else None,
        # Quota-bewust: geen replay/profiling (grootste vreters), en geen PII
        # zoals volledige request-bodies. Gebruiker en organisatie zet de app
        # zelf expliciet op de scope.
        send_default_pii=False,
        profiles_sample_rate=0.0,
    )
    return True
