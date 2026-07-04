from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status

import core
from ai import Narrator
from core.app.portfolio_engine import PortfolioRiskEngine
from core.app.risk_engine import MarginRiskEngine
from core.io.fx import FxDataProvider
from core.models.backtesting import backtest_parametric_var
from core.models.compliance import evaluate_compliance
from core.models.models import OrderInput, SimulationResult
from core.models.monitoring import change_alerts, evaluate_result_alerts
from core.models.monte_carlo import JumpParams
from db import SimulationRecord, SimulationRepository, record_from_result

from .dependencies import get_fx_provider, get_narrator, get_repository, require_api_key
from .schemas import (
    BacktestRequest,
    BacktestResponse,
    ComplianceResponse,
    CurrencyExposureResponse,
    EngineOptions,
    HealthResponse,
    OrderRequest,
    PortfolioRequest,
    PortfolioResponse,
    SimulationRecordResponse,
    SimulationRequest,
    SimulationResponse,
    StressResponse,
)

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])
health_router = APIRouter()


def _record_to_response(record: SimulationRecord) -> SimulationRecordResponse:
    return SimulationRecordResponse(**record.summary())


def _to_order(request: OrderRequest) -> OrderInput:
    return OrderInput(
        amount_foreign=request.amount_foreign,
        foreign_currency=request.foreign_currency,
        domestic_currency=request.domestic_currency,
        order_date=request.resolved_order_date(),
        delivery_date=request.delivery_date,
        expected_revenue_domestic=request.expected_revenue_domestic,
        target_margin_pct=request.target_margin_pct,
        min_acceptable_margin_pct=request.min_acceptable_margin_pct,
        domestic_rate=request.domestic_rate,
        foreign_rate=request.foreign_rate,
        n_simulations=request.n_simulations,
        lookback_days=request.lookback_days,
        seed=request.seed,
    )


def _build_engine(options: EngineOptions, provider: FxDataProvider) -> MarginRiskEngine:
    jumps = None
    if options.jumps is not None:
        jumps = JumpParams(
            intensity_annual=options.jumps.intensity_annual,
            mean_log_jump=options.jumps.mean_log_jump,
            std_log_jump=options.jumps.std_log_jump,
        )
    return MarginRiskEngine(
        fx_provider=provider,
        sampling_method=options.sampling_method,
        volatility_model=options.volatility_model,
        return_distribution=options.return_distribution,
        student_t_dof=options.student_t_dof,
        jumps=jumps,
        market_model=options.market_model,
    )


def _to_simulation_response(
    result: SimulationResult,
    change: list = None,
    narrative: str | None = None,
    record_id: str | None = None,
) -> SimulationResponse:
    return SimulationResponse(
        spot_rate_order_date=result.spot_rate_order_date,
        horizon_days=result.horizon_days,
        annualized_volatility=result.annualized_volatility,
        cip_drift=result.cip_drift,
        expected_terminal_rate=result.expected_terminal_rate,
        breakeven_rate=result.breakeven_rate,
        budgeted_cost_domestic=result.budgeted_cost_domestic,
        budgeted_margin_domestic=result.budgeted_margin_domestic,
        budgeted_margin_pct=result.budgeted_margin_pct,
        rate_percentiles=result.rate_percentiles,
        margin_pct_percentiles=result.margin_pct_percentiles,
        probability_margin_below_threshold=result.probability_margin_below_threshold,
        expected_shortfall_margin_pct=result.expected_shortfall_margin_pct,
        standard_error_margin_pct=result.standard_error_margin_pct,
        vulnerability_score=result.vulnerability_score,
        risk_level=result.risk_level,
        hedge=result.hedge,
        instruments=list(result.instrument_comparison),
        alerts=list(evaluate_result_alerts(result)),
        change_alerts=list(change or []),
        compliance=ComplianceResponse.model_validate(evaluate_compliance(result.order)),
        recommendation=result.recommendation,
        narrative=narrative,
        record_id=record_id,
    )


@health_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=core.__version__)


@router.post("/simulations", response_model=SimulationResponse)
def run_simulation(
    request: SimulationRequest,
    provider: FxDataProvider = Depends(get_fx_provider),
    repository: SimulationRepository = Depends(get_repository),
    narrator: Narrator = Depends(get_narrator),
) -> SimulationResponse:
    order = _to_order(request.order)
    engine = _build_engine(request.options, provider)
    result = engine.run(order)

    previous = repository.latest_for_pair(order.foreign_currency, order.domestic_currency)
    change = []
    if previous is not None:
        change = list(
            change_alerts(
                previous.risk_level,
                previous.vulnerability_score,
                previous.spot_rate,
                result.risk_level,
                result.vulnerability_score,
                result.spot_rate_order_date,
            )
        )

    narrative = narrator.narrate(result) if request.narrative else None

    record_id = None
    if request.persist:
        record = repository.save(record_from_result(result))
        record_id = record.id

    return _to_simulation_response(result, change, narrative, record_id)


@router.get("/simulations/history", response_model=list[SimulationRecordResponse])
def list_history(
    foreign_currency: str | None = Query(default=None, pattern=r"^[A-Za-z]{3}$"),
    domestic_currency: str | None = Query(default=None, pattern=r"^[A-Za-z]{3}$"),
    limit: int = Query(default=50, ge=1, le=500),
    repository: SimulationRepository = Depends(get_repository),
) -> list[SimulationRecordResponse]:
    records = repository.history(
        foreign_currency.upper() if foreign_currency else None,
        domestic_currency.upper() if domestic_currency else None,
        limit,
    )
    return [_record_to_response(record) for record in records]


@router.get("/simulations/{record_id}", response_model=SimulationRecordResponse)
def get_simulation(
    record_id: str, repository: SimulationRepository = Depends(get_repository)
) -> SimulationRecordResponse:
    record = repository.get(record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found.")
    return _record_to_response(record)


@router.get("/exposure", response_model=list[CurrencyExposureResponse])
def currency_exposure(
    repository: SimulationRepository = Depends(get_repository),
) -> list[CurrencyExposureResponse]:
    summary = getattr(repository, "exposure_summary", None)
    rows = summary() if callable(summary) else []
    return [CurrencyExposureResponse(**row) for row in rows]


@router.post("/stress-tests", response_model=StressResponse)
def run_stress_test(
    request: SimulationRequest, provider: FxDataProvider = Depends(get_fx_provider)
) -> StressResponse:
    engine = _build_engine(request.options, provider)
    report = engine.stress_test(_to_order(request.order))
    return StressResponse(
        spot=report.spot,
        budgeted_margin_pct=report.budgeted_margin_pct,
        scenarios=list(report.scenarios),
        reverse_stress=report.reverse_stress,
    )


@router.post("/compliance", response_model=ComplianceResponse)
def check_compliance(request: OrderRequest) -> ComplianceResponse:
    return ComplianceResponse.model_validate(evaluate_compliance(_to_order(request)))


@router.post("/portfolio/simulations", response_model=PortfolioResponse)
def run_portfolio(
    request: PortfolioRequest, provider: FxDataProvider = Depends(get_fx_provider)
) -> PortfolioResponse:
    engine = PortfolioRiskEngine(fx_provider=provider, volatility_model=request.volatility_model)
    result = engine.run([_to_order(order) for order in request.orders], seed=request.seed)
    return PortfolioResponse(
        total_revenue_domestic=result.total_revenue_domestic,
        total_budgeted_cost_domestic=result.total_budgeted_cost_domestic,
        expected_cost_domestic=result.expected_cost_domestic,
        budgeted_margin_pct=result.budgeted_margin_pct,
        expected_margin_pct=result.expected_margin_pct,
        margin_pct_percentiles=result.margin_pct_percentiles,
        cvar_margin_pct=result.cvar_margin_pct,
        undiversified_cvar_margin_pct=result.undiversified_cvar_margin_pct,
        diversification_benefit_pct=result.diversification_benefit_pct,
        cvar_margin_domestic=result.cvar_margin_domestic,
        probability_below_threshold=result.probability_below_threshold,
        vulnerability_score=result.vulnerability_score,
        risk_level=result.risk_level,
        net_exposures=result.net_exposures,
    )


@router.post("/backtests/var", response_model=BacktestResponse)
def run_backtest(
    request: BacktestRequest, provider: FxDataProvider = Depends(get_fx_provider)
) -> BacktestResponse:
    end = dt.date.today()
    start = end - dt.timedelta(days=request.lookback_days)
    series = provider.get_historical_series(
        request.foreign_currency.upper(), request.domestic_currency.upper(), start, end
    )
    result = backtest_parametric_var(series, alpha=request.alpha, window=request.window)
    return BacktestResponse(
        n_observations=result.n_observations,
        n_exceedances=result.n_exceedances,
        expected_exceedance_rate=result.expected_exceedance_rate,
        observed_exceedance_rate=result.observed_exceedance_rate,
        likelihood_ratio=result.likelihood_ratio,
        p_value=result.p_value,
        rejected=result.rejected,
    )
