from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

from ..config import settings
from .enums import HedgeInstrument
from .scoring import conditional_value_at_risk, probability_below_threshold

OptionPricer = Callable[[str, float], float]


def gk_option_pricer(
    spot, domestic_rate, foreign_rate, sigma_annual, horizon_years
) -> OptionPricer:
    def price(kind: str, strike: float) -> float:
        if kind == "call":
            return garman_kohlhagen_call(
                spot, strike, domestic_rate, foreign_rate, sigma_annual, horizon_years
            )
        return garman_kohlhagen_put(
            spot, strike, domestic_rate, foreign_rate, sigma_annual, horizon_years
        )

    return price


def mc_option_pricer(
    simulated_rates: np.ndarray, domestic_rate: float, horizon_years: float
) -> OptionPricer:
    discount = float(np.exp(-domestic_rate * horizon_years))

    def price(kind: str, strike: float) -> float:
        if kind == "call":
            payoff = np.maximum(simulated_rates - strike, 0.0)
        else:
            payoff = np.maximum(strike - simulated_rates, 0.0)
        return discount * float(payoff.mean())

    return price


@dataclass(frozen=True, slots=True)
class InstrumentOutcome:
    instrument: HedgeInstrument
    description: str
    upfront_premium_domestic: float
    expected_margin_pct: float
    cvar_margin_pct: float
    worst_case_margin_pct: float
    best_case_margin_pct: float
    probability_below_threshold: float


def _d1_d2(spot, strike, rd, rf, sigma, t):
    vol = sigma * np.sqrt(t)
    d1 = (np.log(spot / strike) + (rd - rf + 0.5 * sigma**2) * t) / vol
    return d1, d1 - vol


def garman_kohlhagen_call(spot, strike, rd, rf, sigma, t):
    """Garman-Kohlhagen (1983) FX call price (per unit of foreign currency)."""
    if sigma <= 0 or t <= 0:
        return max(spot * np.exp(-rf * t) - strike * np.exp(-rd * t), 0.0)
    d1, d2 = _d1_d2(spot, strike, rd, rf, sigma, t)
    return float(spot * np.exp(-rf * t) * norm.cdf(d1) - strike * np.exp(-rd * t) * norm.cdf(d2))


def garman_kohlhagen_put(spot, strike, rd, rf, sigma, t):
    """Garman-Kohlhagen (1983) FX put price (per unit of foreign currency)."""
    if sigma <= 0 or t <= 0:
        return max(strike * np.exp(-rd * t) - spot * np.exp(-rf * t), 0.0)
    d1, d2 = _d1_d2(spot, strike, rd, rf, sigma, t)
    return float(strike * np.exp(-rd * t) * norm.cdf(-d2) - spot * np.exp(-rf * t) * norm.cdf(-d1))


@dataclass(frozen=True, slots=True)
class OptionGreeks:
    delta: float
    gamma: float
    vega: float
    theta: float
    rho_domestic: float
    rho_foreign: float


def garman_kohlhagen_greeks(spot, strike, rd, rf, sigma, t, kind: str = "call") -> OptionGreeks:
    """Closed-form FX (Garman-Kohlhagen) Greeks. ``vega``/``rho`` are per 1.00
    (100%) move in volatility / rates; ``theta`` is per year."""
    if sigma <= 0 or t <= 0:
        raise ValueError("Greeks require strictly positive volatility and maturity.")
    d1, d2 = _d1_d2(spot, strike, rd, rf, sigma, t)
    disc_f = np.exp(-rf * t)
    disc_d = np.exp(-rd * t)
    pdf_d1 = norm.pdf(d1)
    gamma = disc_f * pdf_d1 / (spot * sigma * np.sqrt(t))
    vega = spot * disc_f * pdf_d1 * np.sqrt(t)
    common_theta = -spot * disc_f * pdf_d1 * sigma / (2.0 * np.sqrt(t))
    if kind == "call":
        delta = disc_f * norm.cdf(d1)
        theta = (
            common_theta + rf * spot * disc_f * norm.cdf(d1) - rd * strike * disc_d * norm.cdf(d2)
        )
        rho_domestic = strike * t * disc_d * norm.cdf(d2)
        rho_foreign = -spot * t * disc_f * norm.cdf(d1)
    else:
        delta = -disc_f * norm.cdf(-d1)
        theta = (
            common_theta - rf * spot * disc_f * norm.cdf(-d1) + rd * strike * disc_d * norm.cdf(-d2)
        )
        rho_domestic = -strike * t * disc_d * norm.cdf(-d2)
        rho_foreign = spot * t * disc_f * norm.cdf(-d1)
    return OptionGreeks(
        delta=float(delta),
        gamma=float(gamma),
        vega=float(vega),
        theta=float(theta),
        rho_domestic=float(rho_domestic),
        rho_foreign=float(rho_foreign),
    )


def zero_cost_collar_cap(spot, floor, rd, rf, sigma, t):
    put_premium = garman_kohlhagen_put(spot, floor, rd, rf, sigma, t)

    def objective(cap):
        return garman_kohlhagen_call(spot, cap, rd, rf, sigma, t) - put_premium

    lower, upper = floor, floor * 5.0
    if objective(lower) * objective(upper) > 0:
        raise ValueError("Unable to construct a zero-cost collar within the bounds.")
    return float(brentq(objective, lower, upper, maxiter=200))


def _summarize(instrument, description, premium, margin_pct, threshold):
    return InstrumentOutcome(
        instrument=instrument,
        description=description,
        upfront_premium_domestic=float(premium),
        expected_margin_pct=float(margin_pct.mean()),
        cvar_margin_pct=conditional_value_at_risk(margin_pct),
        worst_case_margin_pct=float(margin_pct.min()),
        best_case_margin_pct=float(margin_pct.max()),
        probability_below_threshold=probability_below_threshold(margin_pct, threshold),
    )


def compare_instruments(
    revenue: float,
    amount_foreign: float,
    spot: float,
    forward: float,
    sigma_annual: float,
    domestic_rate: float,
    foreign_rate: float,
    horizon_years: float,
    simulated_rates: np.ndarray,
    min_acceptable_margin_pct: float = 0.0,
    collar_floor_width: float = settings.COLLAR_FLOOR_WIDTH,
    option_pricer: OptionPricer | None = None,
) -> tuple[InstrumentOutcome, ...]:
    pricer = option_pricer or gk_option_pricer(
        spot, domestic_rate, foreign_rate, sigma_annual, horizon_years
    )

    def margin_pct(cost_domestic, premium):
        return 1.0 - (cost_domestic + premium) / revenue

    unhedged = _summarize(
        HedgeInstrument.NONE,
        "No hedge: fully exposed to the market.",
        0.0,
        margin_pct(amount_foreign * simulated_rates, 0.0),
        min_acceptable_margin_pct,
    )
    forward_outcome = _summarize(
        HedgeInstrument.FORWARD,
        f"Forward contract at {forward:.4f}: margin locked in.",
        0.0,
        margin_pct(np.full_like(simulated_rates, amount_foreign * forward), 0.0),
        min_acceptable_margin_pct,
    )

    call_premium = amount_foreign * pricer("call", forward)
    option_cost = amount_foreign * np.minimum(simulated_rates, forward)
    option_outcome = _summarize(
        HedgeInstrument.OPTION,
        f"Call option (strike {forward:.4f}): caps the cost, keeps the upside.",
        call_premium,
        margin_pct(option_cost, call_premium),
        min_acceptable_margin_pct,
    )

    floor = forward * (1.0 - collar_floor_width)
    try:
        cap = zero_cost_collar_cap(
            spot, floor, domestic_rate, foreign_rate, sigma_annual, horizon_years
        )
    except ValueError:
        cap = forward * (1.0 + collar_floor_width)
    net_premium = amount_foreign * (pricer("call", cap) - pricer("put", floor))
    collar_cost = amount_foreign * np.clip(simulated_rates, floor, cap)
    collar_outcome = _summarize(
        HedgeInstrument.COLLAR,
        f"Zero-cost collar (floor {floor:.4f}, cap {cap:.4f}): cost bounded with no premium.",
        net_premium,
        margin_pct(collar_cost, net_premium),
        min_acceptable_margin_pct,
    )

    return (unhedged, forward_outcome, option_outcome, collar_outcome)
