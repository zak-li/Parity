from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version

from .app import MarginRiskEngine, PortfolioRiskEngine
from .config import RuntimeConfig, load_runtime_config
from .connectors import (
    Camt053Parser,
    Pain001Generator,
)
from .io import (
    ExchangeRateApiFxDataProvider,
    FrankfurterFxDataProvider,
    FxDataProvider,
    StaticFxDataProvider,
    build_default_fx_provider,
)
from .licensing import ParityLicenseError, init, verify_license
from .models import (
    Alert,
    AlertSeverity,
    ComplianceReport,
    CopulaType,
    DisallowedHostError,
    FxDataError,
    FxVolatilitySmile,
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
    participating_forward_alpha,
    participating_forward_strike,
)
from .reporting import generate_portfolio_excel, generate_simulation_excel

__all__ = [
    "Alert",
    "AlertSeverity",
    "Camt053Parser",
    "ComplianceReport",
    "CopulaType",
    "DisallowedHostError",
    "ExchangeRateApiFxDataProvider",
    "FrankfurterFxDataProvider",
    "FxDataError",
    "FxDataProvider",
    "FxVolatilitySmile",
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
    "Pain001Generator",
    "ParityLicenseError",
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
    "generate_portfolio_excel",
    "generate_simulation_excel",
    "init",
    "kupiec_pof_test",
    "load_runtime_config",
    "participating_forward_alpha",
    "participating_forward_strike",
    "verify_license",
]

try:
    __version__ = _package_version("Parity")
except PackageNotFoundError:
    try:
        __version__ = _package_version("xi")
    except PackageNotFoundError:
        __version__ = "1.0.0"
