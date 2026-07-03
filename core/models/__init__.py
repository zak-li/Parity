from __future__ import annotations

from .backtesting import KupiecResult, backtest_parametric_var, kupiec_pof_test
from .compliance import (
    ComplianceCheck,
    ComplianceConfig,
    ComplianceReport,
    evaluate_compliance,
)
from .dcc import DccResult, estimate_dcc
from .enums import (
    AlertSeverity,
    HedgeInstrument,
    MarketModel,
    ReturnDistribution,
    RiskLevel,
    SamplingMethod,
    VolatilityModel,
)
from .heston import (
    HestonParams,
    default_params_from_volatility,
    simulate_heston_terminal_rates,
)
from .monitoring import (
    Alert,
    MonitoringThresholds,
    change_alerts,
    evaluate_change_alerts,
    evaluate_result_alerts,
)
from .exceptions import (
    DisallowedHostError,
    FxDataError,
    InsufficientDataError,
    InvalidOrderError,
    MarginProtectorError,
    RateLimitError,
    SecurityError,
    SimulationError,
)
from .hedging import HedgeAnalysis, evaluate_hedge, optimal_hedge_ratio
from .instruments import (
    InstrumentOutcome,
    compare_instruments,
    garman_kohlhagen_call,
    garman_kohlhagen_put,
    gk_option_pricer,
    mc_option_pricer,
    zero_cost_collar_cap,
)
from .market_stats import annualized_volatility, spot_rate_on_or_before
from .models import OrderInput, SimulationResult
from .monte_carlo import JumpParams, simulate_terminal_rates, standard_error
from .portfolio import (
    PortfolioPosition,
    PortfolioResult,
    net_exposures,
    simulate_portfolio,
)
from .rates import cip_drift, forward_points, theoretical_forward_rate
from .scoring import (
    conditional_value_at_risk,
    percentiles,
    probability_below_threshold,
    vulnerability_score,
)
from .stress import (
    ReverseStressResult,
    StressOutcome,
    StressReport,
    StressScenario,
    apply_scenarios,
    canonical_scenarios,
    historical_stress_scenario,
    reverse_stress_test,
    worst_adverse_move,
)
from .validation import normalize_currency_code, validate_currency_code
from .volatility import (
    estimate_volatility,
    ewma_annualized_volatility,
    garch_annualized_volatility,
)

__all__ = [
    "Alert",
    "AlertSeverity",
    "ComplianceCheck",
    "ComplianceConfig",
    "ComplianceReport",
    "DccResult",
    "DisallowedHostError",
    "FxDataError",
    "HedgeAnalysis",
    "HedgeInstrument",
    "HestonParams",
    "InstrumentOutcome",
    "InsufficientDataError",
    "InvalidOrderError",
    "JumpParams",
    "KupiecResult",
    "MarginProtectorError",
    "MarketModel",
    "MonitoringThresholds",
    "OrderInput",
    "PortfolioPosition",
    "PortfolioResult",
    "RateLimitError",
    "ReturnDistribution",
    "ReverseStressResult",
    "RiskLevel",
    "SamplingMethod",
    "SecurityError",
    "SimulationError",
    "SimulationResult",
    "StressOutcome",
    "StressReport",
    "StressScenario",
    "VolatilityModel",
    "annualized_volatility",
    "apply_scenarios",
    "backtest_parametric_var",
    "canonical_scenarios",
    "change_alerts",
    "cip_drift",
    "compare_instruments",
    "conditional_value_at_risk",
    "default_params_from_volatility",
    "estimate_dcc",
    "estimate_volatility",
    "evaluate_change_alerts",
    "evaluate_compliance",
    "evaluate_hedge",
    "evaluate_result_alerts",
    "ewma_annualized_volatility",
    "forward_points",
    "garch_annualized_volatility",
    "garman_kohlhagen_call",
    "garman_kohlhagen_put",
    "gk_option_pricer",
    "historical_stress_scenario",
    "mc_option_pricer",
    "simulate_heston_terminal_rates",
    "kupiec_pof_test",
    "net_exposures",
    "normalize_currency_code",
    "optimal_hedge_ratio",
    "percentiles",
    "probability_below_threshold",
    "reverse_stress_test",
    "simulate_portfolio",
    "simulate_terminal_rates",
    "spot_rate_on_or_before",
    "standard_error",
    "theoretical_forward_rate",
    "validate_currency_code",
    "vulnerability_score",
    "worst_adverse_move",
    "zero_cost_collar_cap",
]
