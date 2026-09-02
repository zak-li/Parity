from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from .instruments import OptionPricer, garman_kohlhagen_call, garman_kohlhagen_put


@dataclass(frozen=True, slots=True)
class FxVolatilitySmile:
    """FX Volatility Smile parametrization based on market-standard Malz (1997) formula.

    Calibrated on the 3 standard OTC quotes:
    - ``atm_vol``: At-the-money straddle volatility (sigma_ATM).
    - ``rr_25``: 25-Delta Risk Reversal (sigma_25C - sigma_25P), measuring skew/asymmetry.
    - ``bf_25``: 25-Delta Butterfly (0.5 * (sigma_25C + sigma_25P) - sigma_ATM), measuring smile curvature.
    """

    atm_vol: float
    rr_25: float = 0.0
    bf_25: float = 0.0

    def __post_init__(self) -> None:
        if self.atm_vol <= 0.0:
            raise ValueError("ATM volatility must be strictly positive.")
        if self.bf_25 < 0.0:
            raise ValueError("Butterfly volatility (smile curvature) cannot be negative.")

    def vol_by_delta(self, delta: float) -> float:
        """Evaluate implied volatility for a given foreign currency Call Delta in (0, 1).

        Malz (1997) quadratic interpolation:
        ``sigma(delta) = atm_vol - 2 * rr_25 * (delta - 0.5) + 16 * bf_25 * (delta - 0.5)^2``
        """
        clipped_delta = float(np.clip(delta, 0.01, 0.99))
        diff = clipped_delta - 0.5
        vol = self.atm_vol - 2.0 * self.rr_25 * diff + 16.0 * self.bf_25 * (diff**2)
        return float(max(vol, 1e-4))

    def vol_by_strike(
        self,
        spot: float,
        strike: float,
        rd: float,
        rf: float,
        t: float,
    ) -> float:
        """Evaluate implied volatility for a given strike K using the Garman-Kohlhagen delta mapping."""
        if t <= 0.0 or strike <= 0.0 or spot <= 0.0:
            return self.atm_vol

        vol_atm = self.atm_vol
        d1 = (np.log(spot / strike) + (rd - rf + 0.5 * vol_atm**2) * t) / (vol_atm * np.sqrt(t))
        delta = float(np.exp(-rf * t) * norm.cdf(d1))
        return self.vol_by_delta(delta)

    def build_pricer(
        self,
        spot: float,
        rd: float,
        rf: float,
        t: float,
    ) -> OptionPricer:
        """Return an OptionPricer callback evaluating Garman-Kohlhagen with smile-adjusted volatility."""

        def price(kind: str, strike: float) -> float:
            sigma_k = self.vol_by_strike(spot, strike, rd, rf, t)
            if kind == "call":
                return garman_kohlhagen_call(spot, strike, rd, rf, sigma_k, t)
            return garman_kohlhagen_put(spot, strike, rd, rf, sigma_k, t)

        return price
