from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd

from api.monitoring import CollectingAlertSink, MonitoringScheduler
from api.monitoring.sinks import EmailAlertSink, WebhookAlertSink
from core.app.risk_engine import MarginRiskEngine
from core.io.fx.static import StaticFxDataProvider
from core.models.enums import AlertSeverity
from core.models.monitoring import Alert
from db.memory import InMemorySimulationRepository

ORDER_DATE = dt.date(2026, 1, 15)


def _provider(sigma=0.12, seed=42):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp(ORDER_DATE), periods=260)
    lr = rng.normal(0, sigma / np.sqrt(252), 260)
    lr[0] = 0.0
    return StaticFxDataProvider(pd.Series(10 * np.exp(np.cumsum(lr)), index=dates))


def _order(**overrides):
    from core.models.models import OrderInput

    params = {
        "amount_foreign": 100_000.0,
        "foreign_currency": "USD",
        "domestic_currency": "MAD",
        "order_date": ORDER_DATE,
        "delivery_date": ORDER_DATE + dt.timedelta(days=90),
        "target_margin_pct": 0.15,
        "domestic_rate": 0.03,
        "foreign_rate": 0.05,
        "n_simulations": 5_000,
        "seed": 7,
    }
    params.update(overrides)
    return OrderInput(**params)


def test_scheduler_persists_and_reports_outcomes():
    repo = InMemorySimulationRepository()
    sink = CollectingAlertSink()
    scheduler = MonitoringScheduler(MarginRiskEngine(_provider()), repo, [sink])

    outcomes = scheduler.run_once([_order()])
    assert len(outcomes) == 1
    assert repo.history() != []


def test_scheduler_dispatches_alerts_on_risky_order():
    repo = InMemorySimulationRepository()
    sink = CollectingAlertSink()
    scheduler = MonitoringScheduler(MarginRiskEngine(_provider(sigma=0.5)), repo, [sink])

    risky = _order(target_margin_pct=0.03, min_acceptable_margin_pct=0.10, foreign_rate=0.20)
    outcomes = scheduler.run_once([risky])
    assert outcomes[0].alert_count > 0
    assert outcomes[0].dispatched
    assert sink.dispatched


def test_scheduler_detects_inter_run_change():
    repo = InMemorySimulationRepository()
    sink = CollectingAlertSink()
    engine = MarginRiskEngine(_provider())
    scheduler = MonitoringScheduler(engine, repo, [sink])

    scheduler.run_once([_order()])
    scheduler.run_once(
        [_order(foreign_rate=0.30, min_acceptable_margin_pct=0.10, target_margin_pct=0.05)]
    )

    all_codes = {a.code for _, alerts in sink.dispatched for a in alerts}
    assert all_codes


def test_scheduler_survives_failing_sink():
    class _BoomSink:
        def dispatch(self, subject, alerts):
            raise RuntimeError("sink down")

    repo = InMemorySimulationRepository()
    scheduler = MonitoringScheduler(MarginRiskEngine(_provider(sigma=0.5)), repo, [_BoomSink()])
    outcomes = scheduler.run_once([_order(target_margin_pct=0.03, min_acceptable_margin_pct=0.10)])
    assert outcomes[0].dispatched is False


def test_webhook_sink_posts_payload():
    class _FakeSession:
        def __init__(self):
            self.calls = []

        def post(self, url, data=None, timeout=None, headers=None):
            self.calls.append((url, json.loads(data)))

    session = _FakeSession()
    sink = WebhookAlertSink("https://hooks.example.com/x", session=session)
    sink.dispatch("sujet", [Alert("risk_level", AlertSeverity.CRITICAL, "risque critique")])

    assert session.calls[0][0] == "https://hooks.example.com/x"
    assert session.calls[0][1]["alerts"][0]["code"] == "risk_level"


def test_webhook_sink_swallows_errors():
    class _BoomSession:
        def post(self, *args, **kwargs):
            raise RuntimeError("network down")

    sink = WebhookAlertSink("https://x", session=_BoomSession())
    sink.dispatch("s", [Alert("c", AlertSeverity.INFO, "m")])  # ne doit pas lever


def test_email_sink_sends_via_smtp_factory():
    sent = {}

    class _FakeSMTP:
        def __init__(self, host, port):
            sent["endpoint"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self, context=None):
            sent["tls"] = True

        def login(self, user, password):
            sent["login"] = user

        def send_message(self, message):
            sent["subject"] = message["Subject"]
            sent["body"] = message.get_content()

    sink = EmailAlertSink(
        "smtp.example.com",
        587,
        "from@x.com",
        ["to@x.com"],
        username="u",
        password="p",
        smtp_factory=_FakeSMTP,
    )
    sink.dispatch("Alerte risque", [Alert("score_jump", AlertSeverity.WARNING, "score +20")])

    assert sent["endpoint"] == ("smtp.example.com", 587)
    assert sent["tls"] is True
    assert sent["subject"] == "Alerte risque"
    assert "score_jump" in sent["body"]


def test_email_sink_swallows_errors():
    class _BoomSMTP:
        def __init__(self, *a):
            raise RuntimeError("smtp down")

    sink = EmailAlertSink("h", 25, "f@x", ["t@x"], smtp_factory=_BoomSMTP)
    sink.dispatch("s", [Alert("c", AlertSeverity.INFO, "m")])  # ne doit pas lever


def test_console_sink_logs(caplog):
    from api.monitoring import ConsoleAlertSink

    sink = ConsoleAlertSink()
    with caplog.at_level("WARNING"):
        sink.dispatch("sujet", [Alert("risk_level", AlertSeverity.WARNING, "risque")])
    assert any("alert" in r.message for r in caplog.records)
