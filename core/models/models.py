from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from ..config import settings
from .enums import RiskLevel
from .exceptions import InvalidOrderError
from .hedging import HedgeAnalysis
from .instruments import InstrumentOutcome
from .validation import validate_currency_code


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and np.isfinite(value)
    )


@dataclass(frozen=True, slots=True)
class OrderInput:
    amount_foreign: float
    foreign_currency: str
    domestic_currency: str
    order_date: date
    delivery_date: date
    expected_revenue_domestic: float | None = None
    target_margin_pct: float | None = None
    min_acceptable_margin_pct: float = 0.0
    domestic_rate: float = 0.0
    foreign_rate: float = 0.0
    n_simulations: int = settings.DEFAULT_N_SIMULATIONS
    lookback_days: int = settings.DEFAULT_LOOKBACK_DAYS
    seed: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "foreign_currency", validate_currency_code(self.foreign_currency))
        object.__setattr__(self, "domestic_currency", validate_currency_code(self.domestic_currency))

        if self.foreign_currency == self.domestic_currency:
            raise InvalidOrderError("La devise de la commande et la devise locale doivent être différentes.")
        if not _is_finite_number(self.amount_foreign) or self.amount_foreign <= 0:
            raise InvalidOrderError("Le montant de la commande doit être un nombre fini strictement positif.")
        if not isinstance(self.order_date, date) or not isinstance(self.delivery_date, date):
            raise InvalidOrderError("Les dates doivent être des objets date.")
        if self.delivery_date <= self.order_date:
            raise InvalidOrderError("La date de livraison doit être postérieure à la date de commande.")
        if self.horizon_days > settings.MAX_HORIZON_DAYS:
            raise InvalidOrderError(
                f"L'horizon de simulation ne peut pas dépasser {settings.MAX_HORIZON_DAYS} jours."
            )
        if self.expected_revenue_domestic is None and self.target_margin_pct is None:
            raise InvalidOrderError("Précisez soit le prix de vente attendu, soit une marge cible.")
        if self.expected_revenue_domestic is not None and (
            not _is_finite_number(self.expected_revenue_domestic) or self.expected_revenue_domestic <= 0
        ):
            raise InvalidOrderError("Le prix de vente attendu doit être un nombre fini strictement positif.")
        if self.target_margin_pct is not None and (
            not _is_finite_number(self.target_margin_pct) or self.target_margin_pct <= -1
        ):
            raise InvalidOrderError("La marge cible doit être un nombre fini supérieur à -100%.")
        if not _is_finite_number(self.min_acceptable_margin_pct):
            raise InvalidOrderError("Le seuil de marge acceptable doit être un nombre fini.")
        for label, rate in (("locale", self.domestic_rate), ("étrangère", self.foreign_rate)):
            if not _is_finite_number(rate) or not (
                settings.MIN_RISK_FREE_RATE <= rate <= settings.MAX_RISK_FREE_RATE
            ):
                raise InvalidOrderError(
                    f"Le taux d'intérêt de la devise {label} doit être compris entre "
                    f"{settings.MIN_RISK_FREE_RATE} et {settings.MAX_RISK_FREE_RATE}."
                )
        if not _is_finite_number(self.n_simulations) or not (
            settings.MIN_N_SIMULATIONS <= self.n_simulations <= settings.MAX_N_SIMULATIONS
        ):
            raise InvalidOrderError(
                f"Le nombre de simulations doit être compris entre {settings.MIN_N_SIMULATIONS} "
                f"et {settings.MAX_N_SIMULATIONS}."
            )
        if not _is_finite_number(self.lookback_days) or not (
            settings.MIN_LOOKBACK_DAYS <= self.lookback_days <= settings.MAX_LOOKBACK_DAYS
        ):
            raise InvalidOrderError(
                f"La fenêtre historique doit être comprise entre {settings.MIN_LOOKBACK_DAYS} "
                f"et {settings.MAX_LOOKBACK_DAYS} jours."
            )

    @property
    def horizon_days(self) -> int:
        return (self.delivery_date - self.order_date).days


@dataclass(frozen=True, slots=True)
class SimulationResult:
    order: OrderInput
    spot_rate_order_date: float
    horizon_days: int
    annualized_volatility: float
    cip_drift: float
    expected_terminal_rate: float
    breakeven_rate: float
    budgeted_cost_domestic: float
    budgeted_margin_domestic: float
    budgeted_margin_pct: float
    rate_percentiles: dict[str, float]
    margin_pct_percentiles: dict[str, float]
    probability_margin_below_threshold: float
    expected_shortfall_margin_pct: float
    standard_error_margin_pct: float
    vulnerability_score: int
    risk_level: RiskLevel
    hedge: HedgeAnalysis
    instrument_comparison: tuple[InstrumentOutcome, ...]
    recommendation: str
    simulated_rates: np.ndarray = field(repr=False)
    simulated_margin_pct: np.ndarray = field(repr=False)
