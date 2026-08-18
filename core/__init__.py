from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version

from .app import MarginRiskEngine, PortfolioRiskEngine
from .config import RuntimeConfig, load_runtime_config
from .io import (
    ExchangeRateApiFxDataProvider,
    FrankfurterFxDataProvider,
    FxDataProvider,
    StaticFxDataProvider,
    build_default_fx_provider,
)
from .models import (
    Alert,
    AlertSeverity,
    ComplianceReport,
    DisallowedHostError,
    FxDataError,
    HedgeAnalysis,
    HedgeInstrument,
    InstrumentOutcome,
    InsufficientDataError,
    InvalidOrderError,
    JumpParams,
    KupiecResult,
    MarginProtectorError,
    MonitoringThresholds,
    OrderInput,
    PortfolioPosition,
    PortfolioResult,
    RateLimitError,
    ReturnDistribution,
    RiskLevel,
    SamplingMethod,
    SecurityError,
    SimulationError,
    SimulationResult,
    StressReport,
    VolatilityModel,
    backtest_parametric_var,
    evaluate_change_alerts,
    evaluate_compliance,
    evaluate_result_alerts,
    kupiec_pof_test,
)

__all__ = [
    "Alert",
    "AlertSeverity",
    "ComplianceReport",
    "DisallowedHostError",
    "ExchangeRateApiFxDataProvider",
    "FrankfurterFxDataProvider",
    "FxDataError",
    "FxDataProvider",
    "HedgeAnalysis",
    "HedgeInstrument",
    "InstrumentOutcome",
    "InsufficientDataError",
    "InvalidOrderError",
    "JumpParams",
    "KupiecResult",
    "MarginProtectorError",
    "MarginRiskEngine",
    "MonitoringThresholds",
    "OrderInput",
    "PortfolioPosition",
    "PortfolioResult",
    "PortfolioRiskEngine",
    "RateLimitError",
    "ReturnDistribution",
    "RiskLevel",
    "RuntimeConfig",
    "SamplingMethod",
    "SecurityError",
    "SimulationError",
    "SimulationResult",
    "StaticFxDataProvider",
    "StressReport",
    "VolatilityModel",
    "backtest_parametric_var",
    "build_default_fx_provider",
    "evaluate_change_alerts",
    "evaluate_compliance",
    "evaluate_result_alerts",
    "kupiec_pof_test",
    "load_runtime_config",
]

try:
    __version__ = _package_version("xi")
except PackageNotFoundError:  # running from source without installed metadata
    __version__ = "0.0.0+unknown"
