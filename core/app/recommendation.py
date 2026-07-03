from __future__ import annotations

from ..models.enums import RiskLevel
from ..models.hedging import HedgeAnalysis
from ..models.models import OrderInput

_ACTIONS: dict[RiskLevel, str] = {
    RiskLevel.LOW: (
        "Risque limité: surveillez le taux mais une couverture n'est probablement pas "
        "nécessaire pour cette commande."
    ),
    RiskLevel.MODERATE: (
        "Envisagez de bloquer une partie de l'exposition via un contrat à terme (forward) "
        "auprès de votre banque, ou surveillez de près jusqu'à la livraison."
    ),
    RiskLevel.HIGH: (
        "Recommandation: bloquez le taux de change dès maintenant auprès de votre banque "
        "(contrat à terme) pour sécuriser votre marge."
    ),
    RiskLevel.CRITICAL: (
        "Risque critique: bloquez le taux immédiatement. Contactez votre banque pour un "
        "contrat à terme ou une option de change avant toute nouvelle exposition."
    ),
}

_MAD_NOTICE = (
    " Au Maroc, la couverture de change est encadrée par l'Office des Changes: vérifiez "
    "l'éligibilité de votre opération avant de contacter votre banque."
)


def _hedge_advice(hedge: HedgeAnalysis) -> str:
    points_sign = "prime" if hedge.forward_points >= 0 else "décote"
    return (
        f"Taux à terme théorique (parité des taux): {hedge.theoretical_forward_rate:.4f} "
        f"({points_sign} de {abs(hedge.forward_points):.4f}). En le bloquant, votre marge est "
        f"figée à {hedge.hedged_margin_pct * 100:.1f}%. Couverture optimale conseillée: "
        f"{hedge.optimal_hedge_ratio * 100:.0f}% de l'exposition. Probabilité que ne pas "
        f"couvrir soit plus favorable: {hedge.probability_unhedged_beats_hedge * 100:.0f}%."
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
        f"Taux actuel {pair}: {spot_rate:.4f}. Taux de rupture de marge: {breakeven_rate:.4f} "
        f"(marge nulle si ce niveau est dépassé d'ici {order.horizon_days} jours). "
        f"Probabilité de passer sous le seuil de marge acceptable: {probability_below * 100:.0f}%."
    )
    action = _ACTIONS[risk_level]
    if order.domestic_currency == "MAD":
        action += _MAD_NOTICE
    return f"{base} {_hedge_advice(hedge)} {action}"
