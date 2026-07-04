from __future__ import annotations

from ..models.enums import RiskLevel
from ..models.hedging import HedgeAnalysis
from ..models.models import OrderInput

_ACTIONS: dict[RiskLevel, str] = {
    RiskLevel.LOW: (
        "Limited risk: monitor the rate, but hedging is probably not necessary for this order."
    ),
    RiskLevel.MODERATE: (
        "Consider locking part of the exposure with a forward contract "
        "at your bank, or monitor closely until delivery."
    ),
    RiskLevel.HIGH: (
        "Recommendation: lock in the exchange rate now with your bank "
        "(forward contract) to protect your margin."
    ),
    RiskLevel.CRITICAL: (
        "Critical risk: lock the rate immediately. Contact your bank for a "
        "forward contract or a currency option before taking on any new exposure."
    ),
}

_MAD_NOTICE = (
    " In Morocco, currency hedging is regulated by the Office des Changes: check "
    "your operation's eligibility before contacting your bank."
)


def _hedge_advice(hedge: HedgeAnalysis) -> str:
    points_sign = "premium" if hedge.forward_points >= 0 else "discount"
    return (
        f"Theoretical forward rate (interest rate parity): {hedge.theoretical_forward_rate:.4f} "
        f"({points_sign} of {abs(hedge.forward_points):.4f}). Locking it fixes your margin "
        f"at {hedge.hedged_margin_pct * 100:.1f}%. Recommended optimal hedge: "
        f"{hedge.optimal_hedge_ratio * 100:.0f}% of the exposure. Probability that staying "
        f"unhedged beats the hedge: {hedge.probability_unhedged_beats_hedge * 100:.0f}%."
    )


def build_recommendation(
    order: OrderInput,
    risk_level: RiskLevel,
    spot_rate: float,
    breakeven_rate: float,
    probability_below: float,
    hedge: HedgeAnalysis,
) -> str:
    pair = f"{order.foreign_currency}/{order.domestic_currency}"
    base = (
        f"Current {pair} rate: {spot_rate:.4f}. Margin breakeven rate: {breakeven_rate:.4f} "
        f"(margin is zero if this level is exceeded within {order.horizon_days} days). "
        f"Probability of falling below the acceptable margin threshold: {probability_below * 100:.0f}%."
    )
    action = _ACTIONS[risk_level]
    if order.domestic_currency == "MAD":
        action += _MAD_NOTICE
    return f"{base} {_hedge_advice(hedge)} {action}"
