from __future__ import annotations

import os
from dataclasses import dataclass, field

TRADING_DAYS_PER_YEAR = 252
CALENDAR_DAYS_PER_YEAR = 365.25

DEFAULT_LOOKBACK_DAYS = 180
MIN_LOOKBACK_DAYS = 30
MAX_LOOKBACK_DAYS = 1825

MAX_HORIZON_DAYS = 1825

DEFAULT_N_SIMULATIONS = 20_000
MIN_N_SIMULATIONS = 1_000
MAX_N_SIMULATIONS = 1_000_000

PERCENTILE_POINTS: tuple[int, ...] = (5, 10, 25, 50, 75, 90, 95)
EXPECTED_SHORTFALL_ALPHA = 0.05

VULNERABILITY_SCORE_PROBABILITY_WEIGHT = 0.55
VULNERABILITY_SCORE_SEVERITY_WEIGHT = 0.45

RISK_LOW_MAX_SCORE = 25
RISK_MODERATE_MAX_SCORE = 50
RISK_HIGH_MAX_SCORE = 75

MAX_LOG_GROWTH_EXPONENT = 50.0

MIN_RISK_FREE_RATE = -0.5
MAX_RISK_FREE_RATE = 1.0
HEDGE_RATIO_GRID_STEP = 0.05

EWMA_LAMBDA = 0.94
DEFAULT_STUDENT_T_DOF = 5.0
MIN_STUDENT_T_DOF = 2.5
GARCH_MAX_ITER = 200

HESTON_DEFAULT_KAPPA = 2.0
HESTON_DEFAULT_XI = 0.4
HESTON_DEFAULT_RHO = -0.3
HESTON_STEPS_PER_YEAR = 252
HESTON_MIN_STEPS = 20
HESTON_MAX_STEPS = 512

DCC_DEFAULT_A = 0.02
DCC_DEFAULT_B = 0.95
COLLAR_FLOOR_WIDTH = 0.05
KUPIEC_SIGNIFICANCE = 0.05
CORRELATION_JITTER = 1e-10

CANONICAL_STRESS_SHOCKS: tuple[tuple[str, float], ...] = (
    ("Favorable shock -10%", -0.10),
    ("Moderate shock +7%", 0.07),
    ("Severe shock +15%", 0.15),
    ("Extreme shock +25%", 0.25),
)
CRISIS_WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("2008 financial crisis", "2008-09-01", "2009-03-31"),
    ("COVID-19 2020", "2020-02-01", "2020-05-31"),
)

COMPLIANCE_MAX_FORWARD_HORIZON_DAYS = 365
COMPLIANCE_REGULATED_DOMESTIC_CURRENCY = "MAD"
COMPLIANCE_REQUIRED_DOCUMENTS: tuple[str, ...] = (
    "Proforma invoice or commercial contract",
    "Domiciled import license",
    "Import commitment registered with the bank",
)

MONITORING_MAX_PROBABILITY_BELOW = 0.25
MONITORING_MAX_SCORE = 75
MONITORING_SPOT_MOVE_BAND = 0.03
MONITORING_DELIVERY_PROXIMITY_DAYS = 14
MONITORING_SCORE_JUMP = 15

CURRENCY_CODE_PATTERN = r"[A-Z]{3}"

_ENV_PREFIX = "XI_"


def _env_float(name: str, default: float, *, minimum: float | None = None) -> float:
    raw = os.environ.get(f"{_ENV_PREFIX}{name}")
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid environment variable {_ENV_PREFIX}{name}: {raw!r}.") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{_ENV_PREFIX}{name} must be >= {minimum}.")
    return value


def _env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = os.environ.get(f"{_ENV_PREFIX}{name}")
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid environment variable {_ENV_PREFIX}{name}: {raw!r}.") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{_ENV_PREFIX}{name} must be >= {minimum}.")
    return value


def _env_hosts(name: str, default: frozenset[str]) -> frozenset[str]:
    raw = os.environ.get(f"{_ENV_PREFIX}{name}")
    if raw is None:
        return default
    hosts = frozenset(h.strip().lower() for h in raw.split(",") if h.strip())
    if not hosts:
        raise ValueError(f"{_ENV_PREFIX}{name} cannot be empty.")
    return hosts


def _env_origins(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(f"{_ENV_PREFIX}{name}")
    if raw is None:
        return default
    return tuple(o.strip() for o in raw.split(",") if o.strip())


def _env_tuple(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(f"{_ENV_PREFIX}{name}")
    if raw is None:
        return default
    return tuple(p.strip().lower() for p in raw.split(",") if p.strip())


def _env_str(name: str, default: str | None = None) -> str | None:
    return os.environ.get(f"{_ENV_PREFIX}{name}", default)


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    http_timeout_seconds: float = field(
        default_factory=lambda: _env_float("HTTP_TIMEOUT_SECONDS", 10.0, minimum=0.1)
    )
    http_max_retries: int = field(
        default_factory=lambda: _env_int("HTTP_MAX_RETRIES", 3, minimum=0)
    )
    http_backoff_factor: float = field(
        default_factory=lambda: _env_float("HTTP_BACKOFF_FACTOR", 0.5, minimum=0.0)
    )
    http_max_response_bytes: int = field(
        default_factory=lambda: _env_int("HTTP_MAX_RESPONSE_BYTES", 2_000_000, minimum=1)
    )
    cache_ttl_seconds: float = field(
        default_factory=lambda: _env_float("CACHE_TTL_SECONDS", 3600.0, minimum=1.0)
    )
    cache_max_entries: int = field(
        default_factory=lambda: _env_int("CACHE_MAX_ENTRIES", 256, minimum=1)
    )
    rate_limit_per_second: float = field(
        default_factory=lambda: _env_float("RATE_LIMIT_PER_SECOND", 10.0, minimum=0.01)
    )
    rate_limit_burst: int = field(
        default_factory=lambda: _env_int("RATE_LIMIT_BURST", 20, minimum=1)
    )
    allowed_fx_hosts: frozenset[str] = field(
        default_factory=lambda: _env_hosts(
            "ALLOWED_FX_HOSTS",
            frozenset(
                {
                    "api.frankfurter.dev",
                    "open.er-api.com",
                    "v6.exchangerate-api.com",
                    "api.apilayer.com",
                    "api.fixer.io",
                }
            ),
        )
    )
    fx_providers: tuple[str, ...] = field(
        default_factory=lambda: _env_tuple("FX_PROVIDERS", ("frankfurter", "exchangerate_api"))
    )
    exchangerate_api_key: str | None = field(
        default_factory=lambda: _env_str("EXCHANGERATE_API_KEY", None)
    )
    fixer_api_key: str | None = field(default_factory=lambda: _env_str("FIXER_API_KEY", None))
    auth0_domain: str | None = field(default_factory=lambda: _env_str("AUTH0_DOMAIN", None))
    auth0_client_id: str | None = field(default_factory=lambda: _env_str("AUTH0_CLIENT_ID", None))
    auth0_audience: str = field(
        default_factory=lambda: _env_str("AUTH0_AUDIENCE", "api://default") or "api://default"
    )
    cors_allow_origins: tuple[str, ...] = field(
        default_factory=lambda: _env_origins("CORS_ALLOW_ORIGINS", ())
    )


def _apply_dotenv(env_file: str | os.PathLike[str] | None) -> None:
    try:
        from dotenv import dotenv_values, find_dotenv
    except ImportError:
        return
    path = os.fspath(env_file) if env_file is not None else find_dotenv(usecwd=True)
    if not path:
        return
    for key, value in dotenv_values(path).items():
        if value is not None and key not in os.environ:
            os.environ[key] = value


def load_runtime_config(
    env_file: str | os.PathLike[str] | None = None, *, use_dotenv: bool = True
) -> RuntimeConfig:
    if use_dotenv:
        _apply_dotenv(env_file)
    return RuntimeConfig()
