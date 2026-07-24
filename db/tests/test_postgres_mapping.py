from __future__ import annotations

import datetime as dt

from core.models.enums import RiskLevel
from db.postgres import PostgresSimulationRepository
from db.records import SimulationRecord


def _record(client_id: str = "acme") -> SimulationRecord:
    return SimulationRecord(
        id="rec-1",
        created_at=dt.datetime(2026, 1, 15, tzinfo=dt.UTC),
        foreign_currency="USD",
        domestic_currency="EUR",
        order_date=dt.date(2026, 1, 15),
        delivery_date=dt.date(2026, 4, 15),
        horizon_days=90,
        amount_foreign=1000.0,
        spot_rate=1.10,
        forward_rate=1.09,
        annualized_volatility=0.10,
        budgeted_margin_pct=0.15,
        probability_below_threshold=0.20,
        expected_shortfall_margin_pct=0.05,
        optimal_hedge_ratio=0.50,
        hedged_margin_pct=0.14,
        vulnerability_score=30,
        risk_level=RiskLevel.MODERATE,
        recommendation="hold",
        details={"k": 1},
        client_id=client_id,
    )


def test_row_roundtrip_preserves_tenant_and_fields():
    record = _record("acme")
    row = PostgresSimulationRepository._to_row(record)
    assert row["client_id"] == "acme"
    assert row["pair"] == "USDEUR"

    restored = PostgresSimulationRepository._from_row(row)
    assert restored.client_id == "acme"
    assert restored.id == record.id
    assert restored.risk_level is RiskLevel.MODERATE
    assert restored.amount_foreign == record.amount_foreign


def test_from_row_defaults_tenant_for_legacy_rows():
    row = PostgresSimulationRepository._to_row(_record())
    row.pop("client_id")  # a row written before multi-tenancy
    restored = PostgresSimulationRepository._from_row(row)
    assert restored.client_id == "public"
