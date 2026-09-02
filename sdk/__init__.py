"""Parity: Institutional Quantitative FX Risk & Decision Engine.

Open-source & commercial currency risk decision engine for importers,
treasurers, corporate finance desks, and e-commerce merchants.
"""

from __future__ import annotations

import sys

import core
from core import (
    Alert,
    AlertSeverity,
    Camt053Parser,
    ComplianceReport,
    CopulaType,
    DisallowedHostError,
    ExchangeRateApiFxDataProvider,
    FrankfurterFxDataProvider,
    FxDataError,
    FxDataProvider,
    FxVolatilitySmile,
    HedgeAnalysis,
    HedgeInstrument,
    InstrumentOutcome,
    InsufficientDataError,
    InvalidOrderError,
    JumpParams,
    KupiecResult,
    MarginProtectorError,
    MarginRiskEngine,
    MonitoringThresholds,
    OrderInput,
    Pain001Generator,
    ParityLicenseError,
    PortfolioPosition,
    PortfolioResult,
    PortfolioRiskEngine,
    RateLimitError,
    ReturnDistribution,
    RiskLevel,
    RuntimeConfig,
    SamplingMethod,
    SecurityError,
    SimulationError,
    SimulationResult,
    StaticFxDataProvider,
    StressReport,
    VolatilityModel,
    app,
    backtest_parametric_var,
    build_default_fx_provider,
    cli,
    config,
    connectors,
    evaluate_change_alerts,
    evaluate_compliance,
    evaluate_result_alerts,
    generate_portfolio_excel,
    generate_simulation_excel,
    init,
    io,
    kupiec_pof_test,
    load_runtime_config,
    models,
    participating_forward_alpha,
    participating_forward_strike,
    reporting,
    verify_license,
)

# Register subpackages into sys.modules for direct dotted imports (e.g. from sdk.models import ...)
sys.modules["sdk.app"] = app
sys.modules["sdk.models"] = models
sys.modules["sdk.connectors"] = connectors
sys.modules["sdk.io"] = io
sys.modules["sdk.config"] = config
sys.modules["sdk.cli"] = cli
sys.modules["sdk.reporting"] = reporting

# Also register parity and Parity aliases
sys.modules["parity"] = sys.modules[__name__]
sys.modules["parity.app"] = app
sys.modules["parity.models"] = models
sys.modules["parity.connectors"] = connectors
sys.modules["parity.io"] = io
sys.modules["parity.config"] = config
sys.modules["parity.cli"] = cli
sys.modules["parity.reporting"] = reporting

sys.modules["Parity"] = sys.modules[__name__]
sys.modules["Parity.app"] = app
sys.modules["Parity.models"] = models
sys.modules["Parity.connectors"] = connectors
sys.modules["Parity.io"] = io
sys.modules["Parity.config"] = config
sys.modules["Parity.cli"] = cli
sys.modules["Parity.reporting"] = reporting

__version__ = "1.0.0"

ParityEngine = MarginRiskEngine

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
    "ParityEngine",
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
    "app",
    "backtest_parametric_var",
    "build_default_fx_provider",
    "cli",
    "config",
    "connectors",
    "core",
    "evaluate_change_alerts",
    "evaluate_compliance",
    "evaluate_result_alerts",
    "generate_portfolio_excel",
    "generate_simulation_excel",
    "init",
    "io",
    "kupiec_pof_test",
    "load_runtime_config",
    "models",
    "participating_forward_alpha",
    "participating_forward_strike",
    "reporting",
    "verify_license",
]
