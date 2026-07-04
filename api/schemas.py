from __future__ import annotations

import datetime as dt
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.models.enums import (
    AlertSeverity,
    HedgeInstrument,
    MarketModel,
    ReturnDistribution,
    RiskLevel,
    SamplingMethod,
    VolatilityModel,
)

API_MAX_SIMULATIONS = 200_000
API_MAX_PORTFOLIO_ORDERS = 20

CurrencyCode = Annotated[str, Field(pattern=r"^[A-Za-z]{3}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DomainModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class JumpParamsRequest(StrictModel):
    intensity_annual: float = Field(ge=0.0, le=50.0)
    mean_log_jump: float = Field(ge=-1.0, le=1.0)
    std_log_jump: float = Field(ge=0.0, le=1.0)


class EngineOptions(StrictModel):
    volatility_model: VolatilityModel = VolatilityModel.HISTORICAL
    sampling_method: SamplingMethod = SamplingMethod.PSEUDO_RANDOM
    return_distribution: ReturnDistribution = ReturnDistribution.NORMAL
    student_t_dof: float = Field(default=5.0, gt=2.5, le=100.0)
    jumps: JumpParamsRequest | None = None
    market_model: MarketModel = MarketModel.GBM


class OrderRequest(StrictModel):
    amount_foreign: float = Field(gt=0)
    foreign_currency: CurrencyCode
    domestic_currency: CurrencyCode
    order_date: dt.date | None = None
    delivery_date: dt.date
    expected_revenue_domestic: float | None = Field(default=None, gt=0)
    target_margin_pct: float | None = Field(default=None, gt=-1.0, le=10.0)
    min_acceptable_margin_pct: float = Field(default=0.0, ge=-1.0, le=1.0)
    domestic_rate: float = Field(default=0.0, ge=-0.5, le=1.0)
    foreign_rate: float = Field(default=0.0, ge=-0.5, le=1.0)
    n_simulations: int = Field(default=20_000, ge=1_000, le=API_MAX_SIMULATIONS)
    lookback_days: int = Field(default=180, ge=30, le=1825)
    seed: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _require_revenue_or_margin(self) -> OrderRequest:
        if self.expected_revenue_domestic is None and self.target_margin_pct is None:
            raise ValueError("Provide either expected_revenue_domestic or target_margin_pct.")
        return self

    def resolved_order_date(self) -> dt.date:
        return self.order_date or dt.date.today()


class SimulationRequest(StrictModel):
    order: OrderRequest
    options: EngineOptions = Field(default_factory=EngineOptions)
    persist: bool = True
    narrative: bool = False


class PortfolioRequest(StrictModel):
    orders: list[OrderRequest] = Field(min_length=1, max_length=API_MAX_PORTFOLIO_ORDERS)
    volatility_model: VolatilityModel = VolatilityModel.HISTORICAL
    seed: int | None = Field(default=None, ge=0)


class BacktestRequest(StrictModel):
    foreign_currency: CurrencyCode
    domestic_currency: CurrencyCode
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    window: int = Field(default=250, ge=30, le=1000)
    lookback_days: int = Field(default=900, ge=90, le=1825)


class HedgeResponse(DomainModel):
    theoretical_forward_rate: float
    forward_points: float
    hedged_margin_domestic: float
    hedged_margin_pct: float
    unhedged_expected_margin_pct: float
    unhedged_cvar_margin_pct: float
    probability_unhedged_beats_hedge: float
    optimal_hedge_ratio: float
    optimal_hedge_cvar_margin_pct: float
    cvar_improvement_pct: float


class InstrumentResponse(DomainModel):
    instrument: HedgeInstrument
    description: str
    upfront_premium_domestic: float
    expected_margin_pct: float
    cvar_margin_pct: float
    worst_case_margin_pct: float
    best_case_margin_pct: float
    probability_below_threshold: float


class AlertResponse(DomainModel):
    code: str
    severity: AlertSeverity
    message: str


class ComplianceCheckResponse(DomainModel):
    code: str
    passed: bool
    message: str


class ComplianceResponse(DomainModel):
    applicable: bool
    eligible: bool
    operation: str
    checks: list[ComplianceCheckResponse]
    required_documents: list[str]
    ruleset_version: str
    disclaimer: str


class SimulationResponse(BaseModel):
    spot_rate_order_date: float
    horizon_days: int
    annualized_volatility: float
    cip_drift: float
    expected_terminal_rate: float
    breakeven_rate: float
    budgeted_cost_domestic: float
    budgeted_margin_domestic: float
    budgeted_margin_pct: float
    rate_percentiles: dict[str, float]
    margin_pct_percentiles: dict[str, float]
    probability_margin_below_threshold: float
    expected_shortfall_margin_pct: float
    standard_error_margin_pct: float
    vulnerability_score: int
    risk_level: RiskLevel
    hedge: HedgeResponse
    instruments: list[InstrumentResponse]
    alerts: list[AlertResponse]
    change_alerts: list[AlertResponse]
    compliance: ComplianceResponse
    recommendation: str
    narrative: str | None = None
    record_id: str | None = None


class SimulationRecordResponse(BaseModel):
    id: str
    created_at: str
    foreign_currency: str
    domestic_currency: str
    order_date: str
    delivery_date: str
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
    risk_level: str
    recommendation: str


class CurrencyExposureResponse(BaseModel):
    foreign: str
    domestic: str
    runs: int | None = None
    last_score: float | None = None


class StressScenarioResponse(DomainModel):
    scenario: str
    rate_shock_pct: float
    shocked_rate: float
    margin_domestic: float
    margin_pct: float
    margin_pct_change: float


class ReverseStressResponse(DomainModel):
    target_margin_pct: float
    breaking_rate: float
    required_rate_move_pct: float


class StressResponse(BaseModel):
    spot: float
    budgeted_margin_pct: float
    scenarios: list[StressScenarioResponse]
    reverse_stress: ReverseStressResponse


class PortfolioResponse(BaseModel):
    total_revenue_domestic: float
    total_budgeted_cost_domestic: float
    expected_cost_domestic: float
    budgeted_margin_pct: float
    expected_margin_pct: float
    margin_pct_percentiles: dict[str, float]
    cvar_margin_pct: float
    undiversified_cvar_margin_pct: float
    diversification_benefit_pct: float
    cvar_margin_domestic: float
    probability_below_threshold: float
    vulnerability_score: int
    risk_level: RiskLevel
    net_exposures: dict[str, float]


class BacktestResponse(BaseModel):
    n_observations: int
    n_exceedances: int
    expected_exceedance_rate: float
    observed_exceedance_rate: float
    likelihood_ratio: float
    p_value: float
    rejected: bool


class HealthResponse(BaseModel):
    status: str
    version: str
