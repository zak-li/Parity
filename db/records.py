from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from core.models.enums import RiskLevel
from core.models.models import SimulationResult


def _new_id() -> str:
    return uuid.uuid4().hex


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@dataclass(frozen=True, slots=True)
class SimulationRecord:
    id: str
    created_at: dt.datetime
    foreign_currency: str
    domestic_currency: str
    order_date: dt.date
    delivery_date: dt.date
    horizon_days: int
    amount_foreign: float
    spot_rate: float
    forward_rate: float
    annualized_volatility: float
    budgeted_margin_pct: float
    probability_below_threshold: float
    expected_shortfall_margin_pct: float
    optimal_hedge_ratio: float
    hedged_margin_pct: float
    vulnerability_score: int
    risk_level: RiskLevel
    recommendation: str
    details: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def pair(self) -> str:
        return f"{self.foreign_currency}{self.domestic_currency}"

    def summary(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("details", None)
        data["created_at"] = self.created_at.isoformat()
        data["order_date"] = self.order_date.isoformat()
        data["delivery_date"] = self.delivery_date.isoformat()
        data["risk_level"] = self.risk_level.value
        return data


def record_from_result(
    result: SimulationResult,
    record_id: str | None = None,
    created_at: dt.datetime | None = None,
) -> SimulationRecord:
    order = result.order
    details = {
        "rate_percentiles": result.rate_percentiles,
        "margin_pct_percentiles": result.margin_pct_percentiles,
        "hedge": {
            "theoretical_forward_rate": result.hedge.theoretical_forward_rate,
            "optimal_hedge_ratio": result.hedge.optimal_hedge_ratio,
            "hedged_margin_pct": result.hedge.hedged_margin_pct,
            "cvar_improvement_pct": result.hedge.cvar_improvement_pct,
        },
        "instruments": [
            {
                "instrument": outcome.instrument.value,
                "cvar_margin_pct": outcome.cvar_margin_pct,
                "expected_margin_pct": outcome.expected_margin_pct,
                "upfront_premium_domestic": outcome.upfront_premium_domestic,
            }
            for outcome in result.instrument_comparison
        ],
    }
    return SimulationRecord(
        id=record_id or _new_id(),
        created_at=created_at or _utc_now(),
        foreign_currency=order.foreign_currency,
        domestic_currency=order.domestic_currency,
        order_date=order.order_date,
        delivery_date=order.delivery_date,
        horizon_days=result.horizon_days,
        amount_foreign=order.amount_foreign,
        spot_rate=result.spot_rate_order_date,
        forward_rate=result.expected_terminal_rate,
        annualized_volatility=result.annualized_volatility,
        budgeted_margin_pct=result.budgeted_margin_pct,
        probability_below_threshold=result.probability_margin_below_threshold,
        expected_shortfall_margin_pct=result.expected_shortfall_margin_pct,
        optimal_hedge_ratio=result.hedge.optimal_hedge_ratio,
        hedged_margin_pct=result.hedge.hedged_margin_pct,
        vulnerability_score=result.vulnerability_score,
        risk_level=result.risk_level,
        recommendation=result.recommendation,
        details=details,
    )


@dataclass(frozen=True, slots=True)
class ApiKeyRecord:
    id: str
    client_id: str
    prefix: str
    hashed_key: str
    created_at: dt.datetime
    expires_at: dt.datetime | None = None
    revoked: bool = False


@dataclass(frozen=True, slots=True)
class ApiAuditLogRecord:
    id: int | None
    timestamp: dt.datetime
    client_id: str
    endpoint: str
    method: str
    status_code: int
    processing_time_ms: float


@dataclass(frozen=True, slots=True)
class JobRunRecord:
    id: str
    created_at: dt.datetime
    updated_at: dt.datetime
    status: str
    result_id: str | None = None
    error: str | None = None
