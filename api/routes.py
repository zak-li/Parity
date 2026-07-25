from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from ai import Narrator
from core.app.portfolio_engine import PortfolioRiskEngine
from core.app.risk_engine import MarginRiskEngine
from core.app.tracking import SimulationTracker
from core.io.fx import FxDataProvider
from core.models import market_stats, volatility
from core.models.backtesting import backtest_expected_shortfall, backtest_parametric_var
from core.models.compliance import evaluate_compliance
from core.models.instruments import garman_kohlhagen_greeks
from core.models.ladder import CashflowTranche, simulate_ladder
from core.models.models import OrderInput, SimulationResult
from core.models.monitoring import change_alerts, evaluate_result_alerts
from core.models.monte_carlo import JumpParams
from db import (
    AuthRepository,
    JobRepository,
    JobRunRecord,
    SimulationRecord,
    SimulationRepository,
    record_from_result,
)
from db.records import ApiKeyRecord

from .dependencies import (
    get_auth_repository,
    get_fx_provider,
    get_job_repository,
    get_narrator,
    get_repository,
    get_tracker,
    require_admin,
    require_api_key,
)
from .schemas import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    BacktestRequest,
    BacktestResponse,
    ComplianceResponse,
    CurrencyExposureResponse,
    EngineOptions,
    ESBacktestResponse,
    HealthResponse,
    HedgeGreeksRequest,
    HedgeGreeksResponse,
    IdentityResponse,
    LadderRequest,
    LadderResponse,
    OrderRequest,
    PortfolioRequest,
    PortfolioResponse,
    SimulationRecordResponse,
    SimulationRequest,
    SimulationResponse,
    StressResponse,
)
from .security import generate_api_key

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])
health_router = APIRouter()
keys_router = APIRouter(prefix="/api/v1/keys", tags=["keys"], dependencies=[Depends(require_admin)])


@keys_router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    request: ApiKeyCreateRequest,
    repo: AuthRepository = Depends(get_auth_repository),
) -> ApiKeyCreatedResponse:
    expires_at = (
        dt.datetime.now(dt.UTC) + dt.timedelta(days=request.expires_days)
        if request.expires_days is not None
        else None
    )
    plaintext, record = generate_api_key(request.client_id, expires_at)
    repo.save_api_key(record)
    return ApiKeyCreatedResponse(
        id=record.id,
        client_id=record.client_id,
        prefix=record.prefix,
        created_at=record.created_at.isoformat(),
        expires_at=record.expires_at.isoformat() if record.expires_at else None,
        revoked=record.revoked,
        api_key=plaintext,
    )


@keys_router.get("", response_model=list[ApiKeyResponse])
def list_api_keys(repo: AuthRepository = Depends(get_auth_repository)) -> list[ApiKeyResponse]:
    return [
        ApiKeyResponse(
            id=k.id,
            client_id=k.client_id,
            prefix=k.prefix,
            created_at=k.created_at.isoformat(),
            expires_at=k.expires_at.isoformat() if k.expires_at else None,
            revoked=k.revoked,
        )
        for k in repo.list_api_keys()
    ]


@keys_router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(key_id: str, repo: AuthRepository = Depends(get_auth_repository)) -> Response:
    if not repo.revoke_api_key(key_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No API key with that id."
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _client_id(principal: ApiKeyRecord | None) -> str:
    """Tenant that owns a run. In open dev mode (no auth) everyone shares 'public'."""
    return principal.client_id if principal is not None else "public"


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
    return HealthResponse(status="ok")


def _run_simulation_job(
    job_id: str,
    request: SimulationRequest,
    provider: FxDataProvider,
    repository: SimulationRepository,
    job_repository: JobRepository,
    narrator: Narrator,
    client_id: str = "public",
) -> None:
    try:
        job_repository.update_status(job_id, "IN_PROGRESS")
        order = _to_order(request.order)
        engine = _build_engine(request.options, provider)
        result = engine.run(order)
        record = repository.save(record_from_result(result, client_id=client_id))
        job_repository.update_status(job_id, "COMPLETED", result_id=record.id)
    except Exception as exc:
        job_repository.update_status(job_id, "FAILED", error=str(exc))


@router.post("/simulations", response_model=SimulationResponse)
def run_simulation(
    request: SimulationRequest,
    background_tasks: BackgroundTasks,
    provider: FxDataProvider = Depends(get_fx_provider),
    repository: SimulationRepository = Depends(get_repository),
    job_repository: JobRepository = Depends(get_job_repository),
    narrator: Narrator = Depends(get_narrator),
    tracker: SimulationTracker = Depends(get_tracker),
    principal: ApiKeyRecord | None = Depends(require_api_key),
):
    client_id = _client_id(principal)
    if request.order.n_simulations > 10000:
        job_id = uuid.uuid4().hex
        job_repository.save(
            JobRunRecord(
                id=job_id,
                created_at=dt.datetime.now(dt.UTC),
                updated_at=dt.datetime.now(dt.UTC),
                status="PENDING",
            )
        )
        background_tasks.add_task(
            _run_simulation_job,
            job_id,
            request,
            provider,
            repository,
            job_repository,
            narrator,
            client_id,
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"detail": "Simulation is processing.", "job_id": job_id},
        )

    order = _to_order(request.order)
    engine = _build_engine(request.options, provider)
    result = engine.run(order)

    # Log the run to MLflow (no-op unless XI_MLFLOW_TRACKING_URI is set).
    background_tasks.add_task(tracker.track, result)

    previous = repository.latest_for_pair(
        order.foreign_currency, order.domestic_currency, client_id
    )
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
        record = repository.save(record_from_result(result, client_id=client_id))
        record_id = record.id

    return _to_simulation_response(result, change, narrative, record_id)


@router.get("/simulations/jobs/{job_id}")
def get_job_status(
    job_id: str,
    job_repository: JobRepository = Depends(get_job_repository),
):
    job = job_repository.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    return {
        "id": job.id,
        "status": job.status,
        "result_id": job.result_id,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


@router.get("/simulations/history", response_model=list[SimulationRecordResponse])
def list_history(
    foreign_currency: str | None = Query(default=None, pattern=r"^[A-Za-z]{3}$"),
    domestic_currency: str | None = Query(default=None, pattern=r"^[A-Za-z]{3}$"),
    limit: int = Query(default=50, ge=1, le=500),
    repository: SimulationRepository = Depends(get_repository),
    principal: ApiKeyRecord | None = Depends(require_api_key),
) -> list[SimulationRecordResponse]:
    records = repository.history(
        foreign_currency.upper() if foreign_currency else None,
        domestic_currency.upper() if domestic_currency else None,
        limit,
        client_id=_client_id(principal),
    )
    return [_record_to_response(record) for record in records]


@router.get("/simulations/{record_id}", response_model=SimulationRecordResponse)
def get_simulation(
    record_id: str,
    repository: SimulationRepository = Depends(get_repository),
    principal: ApiKeyRecord | None = Depends(require_api_key),
) -> SimulationRecordResponse:
    record = repository.get(record_id, client_id=_client_id(principal))
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


@router.get("/me", response_model=IdentityResponse)
def whoami(principal: ApiKeyRecord | None = Depends(require_api_key)) -> IdentityResponse:
    """Return the authenticated client's identity (or open access when no auth is configured)."""
    if principal is None:
        return IdentityResponse(authenticated=False)
    return IdentityResponse(
        authenticated=True, client_id=principal.client_id, prefix=principal.prefix
    )


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
        risk_contributions=list(result.risk_contributions),
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


@router.post("/backtests/es", response_model=ESBacktestResponse)
def run_es_backtest(
    request: BacktestRequest, provider: FxDataProvider = Depends(get_fx_provider)
) -> ESBacktestResponse:
    end = dt.date.today()
    start = end - dt.timedelta(days=request.lookback_days)
    series = provider.get_historical_series(
        request.foreign_currency.upper(), request.domestic_currency.upper(), start, end
    )
    result = backtest_expected_shortfall(series, alpha=request.alpha, window=request.window)
    return ESBacktestResponse(
        n_observations=result.n_observations,
        n_exceedances=result.n_exceedances,
        alpha=result.alpha,
        z2_statistic=result.z2_statistic,
        p_value=result.p_value,
        rejected=result.rejected,
    )


@router.post("/hedge/greeks", response_model=HedgeGreeksResponse)
def hedge_greeks(request: HedgeGreeksRequest) -> HedgeGreeksResponse:
    greeks = garman_kohlhagen_greeks(
        request.spot,
        request.strike,
        request.domestic_rate,
        request.foreign_rate,
        request.sigma_annual,
        request.horizon_years,
        request.kind,
    )
    return HedgeGreeksResponse.model_validate(greeks)


@router.post("/ladder/simulations", response_model=LadderResponse)
def run_ladder(
    request: LadderRequest, provider: FxDataProvider = Depends(get_fx_provider)
) -> LadderResponse:
    order_date = dt.date.today()
    max_horizon = max(tranche.horizon_days for tranche in request.tranches)
    lookback_start = order_date - dt.timedelta(days=request.lookback_days)
    history = provider.get_historical_series(
        request.foreign_currency.upper(),
        request.domestic_currency.upper(),
        lookback_start,
        order_date,
    )
    spot = market_stats.spot_rate_on_or_before(history, order_date)
    sigma = volatility.estimate_volatility(history, request.volatility_model, max_horizon)
    result = simulate_ladder(
        [CashflowTranche(t.label, t.horizon_days, t.amount_foreign) for t in request.tranches],
        spot=spot,
        sigma_annual=sigma,
        domestic_rate=request.domestic_rate,
        foreign_rate=request.foreign_rate,
        target_margin_pct=request.target_margin_pct,
        n_sims=request.n_simulations,
        seed=request.seed,
        min_acceptable_margin_pct=request.min_acceptable_margin_pct,
    )
    return LadderResponse(
        total_amount_foreign=result.total_amount_foreign,
        total_revenue_domestic=result.total_revenue_domestic,
        budgeted_margin_pct=result.budgeted_margin_pct,
        unhedged_expected_margin_pct=result.unhedged_expected_margin_pct,
        unhedged_cvar_margin_pct=result.unhedged_cvar_margin_pct,
        layered_hedged_margin_pct=result.layered_hedged_margin_pct,
        cvar_improvement_pct=result.cvar_improvement_pct,
        probability_below_threshold=result.probability_below_threshold,
        vulnerability_score=result.vulnerability_score,
        risk_level=result.risk_level,
        margin_pct_percentiles=result.margin_pct_percentiles,
        tranches=list(result.tranches),
    )
