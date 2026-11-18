"""Tests voor ``rgs_django_utils.observability``.

Alles hier is pure logica: er wordt geen SDK geïnitialiseerd en er gaat niets
naar Sentry. Waar de aanroep van de SDK ertoe doet, is ``sentry_sdk.init``
gemockt.
"""

import logging
import logging.config
import sys
import types
from unittest import mock

import pytest
from django.http import Http404
from django.test import override_settings
from ninja.errors import AuthenticationError, HttpError, ValidationError

from rgs_django_utils import observability
from rgs_django_utils.observability import (
    HEALTH_PATHS,
    LOG_RECORDS_TOTAL,
    TASK_OP,
    PrometheusLogCounterHandler,
    before_breadcrumb,
    before_send,
    before_send_redacted,
    build_logging_config,
    init_sentry,
    is_interactive_shell,
    make_traces_sampler,
    parse_log_levels,
    redact_kuma_url,
    sentry_task_middleware,
    silence_http_loggers,
)
from rgs_django_utils.utils.authorization import UnauthorizedError

DSN = "https://publiek@sentry.invalid/1"

# ── parse_log_levels ────────────────────────────────────────────────────────


def test_parse_log_levels_normaliseert_geldige_paren():
    assert parse_log_levels("core.tasks.imports=DEBUG, django.db=warning") == {
        "core.tasks.imports": "DEBUG",
        "django.db": "WARNING",
    }


def test_parse_log_levels_slaat_ongeldige_paren_over(caplog):
    """Een typefout in de env legt niets plat: ongeldig = overslaan, met waarschuwing."""
    with caplog.at_level(logging.WARNING, logger="rgs_django_utils.observability"):
        assert parse_log_levels("kapot,x=NOPE,=DEBUG,core=INFO") == {"core": "INFO"}
    assert sum("ongeldig paar" in r.getMessage() for r in caplog.records) == 3


@pytest.mark.parametrize("spec", ["", None, " , ,"])
def test_parse_log_levels_leeg(spec):
    assert parse_log_levels(spec) == {}


# ── build_logging_config ────────────────────────────────────────────────────


def test_build_logging_config_zet_root_en_per_module_niveaus():
    config = build_logging_config("WARNING", {"core.tasks": "DEBUG"})
    assert config["root"]["level"] == "WARNING"
    assert config["loggers"]["core.tasks"] == {"level": "DEBUG", "propagate": True}
    assert config["root"]["handlers"] == ["console", "prometheus_counter"]
    assert config["disable_existing_loggers"] is False


def test_build_logging_config_standaard():
    config = build_logging_config()
    assert config["root"]["level"] == "INFO"
    assert config["loggers"] == {}


def test_build_logging_config_is_laadbaar_door_dictconfig():
    """De handler-klasse in de config moet een bestaand importpad zijn."""
    config = build_logging_config()
    pad = config["handlers"]["prometheus_counter"]["class"]
    assert pad == "rgs_django_utils.observability.PrometheusLogCounterHandler"
    handlers = logging.config.DictConfigurator(config).configure_handler(
        dict(config["handlers"]["prometheus_counter"])
    )
    assert isinstance(handlers, PrometheusLogCounterHandler)
    assert handlers.level == logging.WARNING


# ── Prometheus-logteller ────────────────────────────────────────────────────


def _teller(module, level):
    return LOG_RECORDS_TOTAL.labels(module=module, level=level)._value.get()


def test_logteller_telt_per_top_level_module():
    """Een WARNING telt mee onder het eerste segment van de loggernaam."""
    handler = PrometheusLogCounterHandler()
    voor = _teller("core", "WARNING")
    handler.emit(logging.LogRecord("core.tasks.imports", logging.WARNING, __file__, 1, "let op", (), None))
    assert _teller("core", "WARNING") == voor + 1


def test_logteller_noemt_een_naamloze_logger_root():
    handler = PrometheusLogCounterHandler()
    voor = _teller("root", "ERROR")
    handler.emit(logging.LogRecord("", logging.ERROR, __file__, 1, "stuk", (), None))
    assert _teller("root", "ERROR") == voor + 1


def test_logteller_laat_logging_nooit_falen():
    """Een fout in de teller gaat naar ``handleError``, niet naar de aanroeper."""
    handler = PrometheusLogCounterHandler()
    record = logging.LogRecord("core", logging.WARNING, __file__, 1, "let op", (), None)
    with (
        mock.patch.object(LOG_RECORDS_TOTAL, "labels", side_effect=RuntimeError("teller stuk")),
        mock.patch.object(handler, "handleError") as handle_error,
    ):
        handler.emit(record)
    handle_error.assert_called_once_with(record)


# ── traces_sampler ──────────────────────────────────────────────────────────


def test_celery_taak_wordt_volledig_gesampled():
    sampler = make_traces_sampler(web_rate=0.05, task_rate=1.0)
    assert sampler({"celery_job": {"task": "core.tasks.import"}}) == 1.0


def test_procrastinate_taak_wordt_volledig_gesampled():
    sampler = make_traces_sampler(web_rate=0.05, task_rate=1.0)
    assert sampler({"transaction_context": {"op": TASK_OP, "name": "aanvraag.tasks.heartbeat"}}) == 1.0


def test_taak_volgt_de_task_rate():
    sampler = make_traces_sampler(web_rate=0.05, task_rate=0.25)
    assert sampler({"celery_job": {"task": "x"}}) == 0.25
    assert sampler({"transaction_context": {"op": TASK_OP, "name": "x"}}) == 0.25


def test_uitgesloten_taak_wordt_niet_gesampled():
    """Elke minuut een transactie is 1440 per dag aan Sentry-quota zonder waarde."""
    sampler = make_traces_sampler(unsampled_tasks={"aanvraag.tasks.kuma_heartbeat"})
    assert sampler({"transaction_context": {"op": TASK_OP, "name": "aanvraag.tasks.kuma_heartbeat"}}) == 0.0
    assert sampler({"celery_job": {"task": "aanvraag.tasks.kuma_heartbeat"}}) == 0.0
    assert sampler({"celery_job": {"task": "aanvraag.tasks.import"}}) == 1.0


def test_zonder_uitgesloten_taken_wordt_elke_taak_gesampled():
    sampler = make_traces_sampler()
    assert sampler({"transaction_context": {"op": TASK_OP, "name": "aanvraag.tasks.kuma_heartbeat"}}) == 1.0


def test_celery_job_zonder_taaknaam_valt_niet_om():
    sampler = make_traces_sampler(unsampled_tasks={"x"})
    assert sampler({"celery_job": {}}) == 1.0
    assert sampler({"celery_job": "geen dict"}) == 1.0


@pytest.mark.parametrize("path", HEALTH_PATHS)
def test_health_check_wordt_nooit_gesampled(path):
    sampler = make_traces_sampler()
    assert sampler({"asgi_scope": {"path": path}}) == 0.0
    assert sampler({"wsgi_environ": {"PATH_INFO": path}}) == 0.0


def test_standaard_health_paths():
    assert HEALTH_PATHS == ("/livez/", "/readyz/", "/health/", "/metrics")


def test_eigen_health_paths_vervangen_de_standaard():
    sampler = make_traces_sampler(web_rate=0.05, health_paths=("/ping/",))
    assert sampler({"asgi_scope": {"path": "/ping/"}}) == 0.0
    assert sampler({"asgi_scope": {"path": "/livez/"}}) == 0.05


def test_gewoon_request_krijgt_de_web_rate():
    sampler = make_traces_sampler(web_rate=0.05)
    assert sampler({"asgi_scope": {"path": "/api/me"}}) == 0.05
    assert sampler({}) == 0.05


@pytest.mark.parametrize(("parent", "verwacht"), [(True, 1.0), (False, 0.0)])
def test_beslissing_van_de_frontend_wordt_gerespecteerd(parent, verwacht):
    """Een browser-trace mag niet halverwege de keten afbreken."""
    sampler = make_traces_sampler(web_rate=0.05)
    assert sampler({"asgi_scope": {"path": "/api/me"}, "parent_sampled": parent}) == verwacht


def test_health_check_wint_van_de_ouderbeslissing():
    sampler = make_traces_sampler()
    assert sampler({"asgi_scope": {"path": "/metrics"}, "parent_sampled": True}) == 0.0


# ── before_send ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "exc",
    [
        Http404("weg"),
        PermissionError("mag niet"),
        UnauthorizedError("geen token"),
        AuthenticationError(),
        ValidationError([]),
        HttpError(404, "weg"),
        HttpError(422, "onbruikbare invoer"),
    ],
)
def test_verwachte_fouten_gaan_niet_naar_sentry(exc):
    assert before_send({"x": 1}, {"exc_info": (type(exc), exc, None)}) is None


@pytest.mark.parametrize("exc", [HttpError(500, "stuk"), HttpError(503, "database plat"), ValueError("kapot")])
def test_onverwachte_fouten_gaan_wel_naar_sentry(exc):
    event = {"x": 1}
    assert before_send(event, {"exc_info": (type(exc), exc, None)}) is event


def test_event_zonder_exception_blijft_ongemoeid():
    event = {"message": "iets"}
    assert before_send(event, {}) is event


# ── interactieve shell ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("argv", "verwacht"),
    [
        (["manage.py", "shell"], True),
        (["manage.py", "shell_plus", "-v", "2"], True),
        (["manage.py", "shell", "-c", "print(1)"], True),
        (["manage.py", "--settings=x", "shell_plus"], True),
        (["/app/backend/manage.py", "dbshell"], True),
        # Django zet opties ná het subcommando; een losse optiewaarde vóór het
        # subcommando (`-v 2 shell`) wordt aangezien voor het commando zelf en
        # levert dus False. Vastgelegd omdat het een bewuste grens is, geen bug
        # die stilletjes mag verschuiven.
        (["manage.py", "-v", "2", "shell"], False),
        (["manage.py", "migrate"], False),
        (["manage.py", "test", "core"], False),
        (["manage.py", "procrastinate", "worker"], False),
        (["uvicorn", "thissite.asgi:application"], False),
        (["celery", "-A", "thissite", "worker"], False),
        (["manage.py"], False),
    ],
)
def test_interactieve_shell_herkenning(argv, verwacht):
    assert is_interactive_shell(argv) is verwacht


def test_interactieve_shell_leest_standaard_sys_argv(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["manage.py", "dbshell"])
    assert is_interactive_shell() is True


# ── init_sentry ─────────────────────────────────────────────────────────────


def _init(monkeypatch, argv=("manage.py", "runserver"), **kwargs):
    """Roep ``init_sentry`` aan met een gemockte SDK en geef de init-kwargs terug."""
    monkeypatch.setattr(sys, "argv", list(argv))
    with mock.patch("sentry_sdk.init") as sdk_init:
        resultaat = init_sentry(dsn=DSN, environment=kwargs.pop("environment", "dev"), release="r", **kwargs)
    return resultaat, sdk_init


def test_init_sentry_doet_niets_zonder_dsn():
    """Lokale dev: geen DSN, dus geen SDK en geen foutmelding bij opstarten."""
    with mock.patch("sentry_sdk.init") as sdk_init:
        assert init_sentry(dsn="", environment="development", release="x") is False
        assert init_sentry(dsn=None, environment="development", release="x") is False
    sdk_init.assert_not_called()


def test_init_sentry_slaat_een_handmatige_shell_over(monkeypatch):
    """Ook mét DSN blijft de SDK uit in een handmatige ``manage.py shell``."""
    resultaat, sdk_init = _init(monkeypatch, argv=("manage.py", "shell", "-c", "print(1)"))
    assert resultaat is False
    sdk_init.assert_not_called()


def test_init_sentry_draait_buiten_een_shell(monkeypatch):
    resultaat, sdk_init = _init(monkeypatch)
    assert resultaat is True
    sdk_init.assert_called_once()
    kwargs = sdk_init.call_args.kwargs
    assert kwargs["dsn"] == DSN
    assert kwargs["environment"] == "dev"
    assert kwargs["release"] == "r"
    assert kwargs["send_default_pii"] is False
    assert kwargs["profiles_sample_rate"] == 0.0


def test_init_sentry_standaard_zonder_celery_en_zonder_redactie(monkeypatch):
    """De standaard is de kale variant: Django + logging, alleen het ruisfilter."""
    _, sdk_init = _init(monkeypatch)
    kwargs = sdk_init.call_args.kwargs
    assert [type(i).__name__ for i in kwargs["integrations"]] == ["DjangoIntegration", "LoggingIntegration"]
    assert kwargs["before_send"] is before_send
    assert kwargs["before_breadcrumb"] is None


def test_init_sentry_met_kuma_redactie(monkeypatch):
    _, sdk_init = _init(monkeypatch, redact_kuma=True)
    kwargs = sdk_init.call_args.kwargs
    assert kwargs["before_send"] is before_send_redacted
    assert kwargs["before_breadcrumb"] is before_breadcrumb


def test_init_sentry_geeft_de_sampler_instellingen_door(monkeypatch):
    _, sdk_init = _init(
        monkeypatch,
        web_rate=0.1,
        task_rate=0.5,
        health_paths=("/ping/",),
        unsampled_tasks={"app.tasks.heartbeat"},
    )
    sampler = sdk_init.call_args.kwargs["traces_sampler"]
    assert sampler({"asgi_scope": {"path": "/api/x"}}) == 0.1
    assert sampler({"celery_job": {"task": "app.tasks.import"}}) == 0.5
    assert sampler({"asgi_scope": {"path": "/ping/"}}) == 0.0
    assert sampler({"transaction_context": {"op": TASK_OP, "name": "app.tasks.heartbeat"}}) == 0.0


def _init_met_celery(monkeypatch, environment):
    """Draai ``init_sentry(celery=True)`` met een nagemaakte CeleryIntegration.

    ``sentry_sdk.integrations.celery`` importeert Celery zelf; dat pakket hoort
    niet in de testomgeving van de lib.
    """
    nep = types.ModuleType("sentry_sdk.integrations.celery")
    nep.CeleryIntegration = mock.Mock(name="CeleryIntegration")
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.celery", nep)
    _, sdk_init = _init(monkeypatch, argv=("celery", "-A", "thissite", "beat"), environment=environment, celery=True)
    return nep.CeleryIntegration, sdk_init


def test_init_sentry_met_celery_zet_de_integratie_tussen_django_en_logging(monkeypatch):
    celery_integration, sdk_init = _init_met_celery(monkeypatch, "prod")
    integrations = sdk_init.call_args.kwargs["integrations"]
    assert type(integrations[0]).__name__ == "DjangoIntegration"
    assert integrations[1] is celery_integration.return_value
    assert type(integrations[2]).__name__ == "LoggingIntegration"


@pytest.mark.parametrize(
    ("environment", "verwacht"), [("preview", False), ("dev", True), ("staging", True), ("prod", True)]
)
def test_beat_monitors_alleen_in_langlevende_omgevingen(monkeypatch, environment, verwacht):
    """In ``preview`` blijven na het opruimen anders missed check-ins achter."""
    celery_integration, _ = _init_met_celery(monkeypatch, environment)
    assert celery_integration.call_args.kwargs["monitor_beat_tasks"] is verwacht


# ── Procrastinate-middleware ────────────────────────────────────────────────


class _Job:
    id = 42
    task_name = "aanvraag.tasks.heartbeat"
    queue = "default"


class _Context:
    job = _Job()


def test_task_middleware_geeft_het_resultaat_door():
    assert sentry_task_middleware(lambda: "klaar", _Context(), None) == "klaar"


def test_task_middleware_laat_de_fout_door_naar_procrastinate():
    """Procrastinate moet zijn eigen retry-/foutafhandeling houden."""

    def klapt():
        raise RuntimeError("taak mislukt")

    with pytest.raises(RuntimeError, match="taak mislukt"):
        sentry_task_middleware(klapt, _Context(), None)


def test_task_middleware_werkt_zonder_jobcontext():
    """Een context zonder job mag de worker niet alsnog laten omvallen."""

    class Leeg:
        pass

    assert sentry_task_middleware(lambda: 1, Leeg(), None) == 1


def test_task_middleware_opent_een_transactie_met_taaknaam_en_tags():
    scope = mock.MagicMock()
    with (
        mock.patch("sentry_sdk.isolation_scope") as isolation_scope,
        mock.patch("sentry_sdk.start_transaction") as start_transaction,
        mock.patch("sentry_sdk.capture_exception") as capture_exception,
    ):
        isolation_scope.return_value.__enter__.return_value = scope
        sentry_task_middleware(lambda: None, _Context(), None)
    start_transaction.assert_called_once_with(op=TASK_OP, name="aanvraag.tasks.heartbeat")
    scope.set_tag.assert_any_call("procrastinate.task", "aanvraag.tasks.heartbeat")
    scope.set_tag.assert_any_call("procrastinate.queue", "default")
    scope.set_context.assert_called_once_with("procrastinate", {"job_id": 42, "task": "aanvraag.tasks.heartbeat"})
    capture_exception.assert_not_called()


def test_task_middleware_meldt_een_klappende_taak():
    with mock.patch("sentry_sdk.capture_exception") as capture_exception:
        with pytest.raises(RuntimeError):
            sentry_task_middleware(mock.Mock(side_effect=RuntimeError("stuk")), _Context(), None)
    capture_exception.assert_called_once_with()


def test_logniveau_van_de_module_blijft_ongemoeid():
    """De eigen logger van de module blijft op NOTSET en erft dus van de root."""
    assert logging.getLogger("rgs_django_utils.observability").level == logging.NOTSET
    assert observability.logger.name == "rgs_django_utils.observability"


# ── httpx-loggers ───────────────────────────────────────────────────────────


def test_httpx_logger_logt_geen_info():
    for naam in ("httpx", "httpcore"):
        logging.getLogger(naam).setLevel(logging.NOTSET)
    silence_http_loggers()
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


# ── Kuma push-URL niet in Sentry ────────────────────────────────────────────

KUMA_URL = "https://kuma.example/api/push/GEHEIM123"
KUMA_URL_MET_QUERY = "https://kuma.example/api/push/GEHEIM12345?status=up&msg=OK&ping="


def _lekkend_event():
    return {
        "logentry": {"message": f"HTTP Request: GET {KUMA_URL} 200"},
        "breadcrumbs": {"values": [{"category": "httplib", "data": {"url": KUMA_URL}}]},
        "exception": {
            "values": [
                {
                    "value": f"ConnectError voor {KUMA_URL}",
                    "stacktrace": {"frames": [{"vars": {"url": KUMA_URL, "n": 3}}]},
                }
            ]
        },
    }


def test_redact_kuma_url_verwijdert_de_url_overal():
    with override_settings(KUMA_HEARTBEAT_URL=KUMA_URL):
        resultaat = redact_kuma_url(_lekkend_event())
    assert "GEHEIM123" not in repr(resultaat)
    assert resultaat["breadcrumbs"]["values"][0]["data"]["url"] == "[kuma-heartbeat-url]"
    assert resultaat["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]["n"] == 3


def test_redact_kuma_url_doet_niets_zonder_url():
    with override_settings(KUMA_HEARTBEAT_URL=""):
        assert redact_kuma_url(_lekkend_event()) == _lekkend_event()


def test_redact_kuma_url_doet_niets_zonder_setting():
    """Een app zonder Kuma-heartbeat heeft de setting helemaal niet."""
    from django.conf import settings

    assert not hasattr(settings, "KUMA_HEARTBEAT_URL")
    assert redact_kuma_url(_lekkend_event()) == _lekkend_event()


def test_before_send_redacted_en_before_breadcrumb_redigeren_de_url():
    with override_settings(KUMA_HEARTBEAT_URL=KUMA_URL):
        assert "GEHEIM123" not in repr(before_send_redacted(_lekkend_event(), {}))
        crumb = before_breadcrumb({"category": "httplib", "data": {"url": KUMA_URL}}, {})
    assert "GEHEIM123" not in repr(crumb)


def test_before_send_redacted_filtert_ook_de_ruis():
    exc = PermissionError("mag niet")
    with override_settings(KUMA_HEARTBEAT_URL=KUMA_URL):
        assert before_send_redacted(_lekkend_event(), {"exc_info": (type(exc), exc, None)}) is None


def test_before_send_zelf_redigeert_niet():
    """Het kale ruisfilter laat het event onaangeroerd, ook met de setting gezet."""
    with override_settings(KUMA_HEARTBEAT_URL=KUMA_URL):
        assert before_send(_lekkend_event(), {}) == _lekkend_event()


def test_redact_vangt_url_zonder_query_pad_en_kaal_token():
    event = {
        "breadcrumbs": {
            "values": [
                {"data": {"url": "https://kuma.example/api/push/GEHEIM12345", "http.query": "status=up&msg=OK&ping="}}
            ]
        },
        "exception": {"values": [{"value": "404 voor /api/push/GEHEIM12345"}]},
        "logentry": {"message": "token GEHEIM12345 ongeldig"},
    }
    with override_settings(KUMA_HEARTBEAT_URL=KUMA_URL_MET_QUERY):
        resultaat = redact_kuma_url(event)
    assert "GEHEIM12345" not in repr(resultaat)


def test_redact_laat_korte_laatste_segmenten_met_rust():
    with override_settings(KUMA_HEARTBEAT_URL="https://kuma.example/up"):
        assert redact_kuma_url("de service is up") == "de service is up"
        assert "kuma.example" not in redact_kuma_url("zie https://kuma.example/up nu")


def test_redact_gooit_nooit_bij_rare_waarde():
    with override_settings(KUMA_HEARTBEAT_URL="http://[::1"):
        assert redact_kuma_url({"a": "http://[::1 x"}) == {"a": "[kuma-heartbeat-url] x"}


def test_redact_negeert_een_niet_string_setting():
    with override_settings(KUMA_HEARTBEAT_URL=12345):
        assert redact_kuma_url({"a": "12345"}) == {"a": "12345"}


def test_redact_push_url_zonder_pad_laat_de_hostnaam_staan():
    with override_settings(KUMA_HEARTBEAT_URL="https://kuma.example"):
        resultaat = redact_kuma_url({"a": "verbinding met kuma.example mislukt", "b": "https://kuma.example"})
    assert resultaat["a"] == "verbinding met kuma.example mislukt"
    assert resultaat["b"] == "[kuma-heartbeat-url]"


def test_redact_werkt_lijsten_bij_en_bouwt_tuples_opnieuw():
    lijst = [KUMA_URL, 1]
    event = {"lijst": lijst, "tuple": (KUMA_URL, None)}
    with override_settings(KUMA_HEARTBEAT_URL=KUMA_URL):
        resultaat = redact_kuma_url(event)
    assert resultaat is event
    assert resultaat["lijst"] is lijst
    assert lijst == ["[kuma-heartbeat-url]", 1]
    assert resultaat["tuple"] == ("[kuma-heartbeat-url]", None)


def test_redact_overleeft_een_kringverwijzing():
    event = {"url": KUMA_URL}
    event["zelf"] = event
    lijst = [event]
    event["lijst"] = lijst
    with override_settings(KUMA_HEARTBEAT_URL=KUMA_URL):
        resultaat = redact_kuma_url(event)
    assert resultaat["url"] == "[kuma-heartbeat-url]"
    assert resultaat["zelf"] is event


def test_redact_stopt_bij_een_zeer_diepe_nesting():
    diep = {"url": KUMA_URL}
    for _ in range(5000):
        diep = {"n": diep}
    with override_settings(KUMA_HEARTBEAT_URL=KUMA_URL):
        resultaat = redact_kuma_url(diep)  # geen RecursionError
    niveau = resultaat
    while isinstance(niveau, dict):  # iteratief aflopen: repr zou zelf diep recursen
        niveau = niveau["n"]
    assert niveau == "[te diep genest]"
