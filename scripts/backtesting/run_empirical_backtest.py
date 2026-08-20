from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

from core.io.fx.frankfurter import FrankfurterFxDataProvider
from core.models.backtesting import (
    backtest_parametric_var,
    kupiec_pof_test,
)


def run_student_t_var_backtest(
    series: pd.Series, alpha: float, window: int, df: float = 4.0
) -> dict:
    """Backtest VaR under a heavy-tailed Student-t distribution (df=4.0)."""
    returns = pd.Series(np.log(series / series.shift(1)).dropna().to_numpy())
    if len(returns) <= window:
        raise ValueError("Series too short for window")

    # Quantile multiplier for Student-t normalized to unit variance
    scale_factor = np.sqrt((df - 2.0) / df)
    t_quant = student_t.ppf(alpha, df=df) * scale_factor

    rolling_mean = returns.rolling(window).mean()
    rolling_std = returns.rolling(window).std(ddof=1)
    threshold = (rolling_mean + t_quant * rolling_std).shift(1)

    valid = threshold.notna()
    realized_ret = returns[valid].to_numpy()
    thresh_val = threshold[valid].to_numpy()

    exceedances_indicator = (realized_ret < thresh_val).astype(int)
    n_obs = len(exceedances_indicator)
    n_exceedances = int(exceedances_indicator.sum())

    kup = kupiec_pof_test(n_obs, n_exceedances, alpha)
    lr_stat, p_val = kup.likelihood_ratio, kup.p_value

    return {
        "n_obs": n_obs,
        "n_exceedances": n_exceedances,
        "expected": n_obs * alpha,
        "rate": n_exceedances / n_obs,
        "kupiec_lr": lr_stat,
        "kupiec_pval": p_val,
        "kupiec_rej": p_val < 0.05,
    }


def main():
    print("=" * 80)
    print("EMPIRICAL BACKTESTING SUITE (GAUSSIAN VS STUDENT-T)")
    print("=" * 80)
    provider = FrankfurterFxDataProvider()
    start_date = dt.date(2021, 1, 1)
    end_date = dt.date(2026, 2, 1)

    series_eur_usd = provider.get_historical_series("EUR", "USD", start_date, end_date)
    series_usd_eur = 1.0 / series_eur_usd

    # 1. Standard Gaussian VaR Backtest
    res_gauss = backtest_parametric_var(series_usd_eur, alpha=0.05, window=180)
    print(
        f"Gaussian VaR 95%: Obs={res_gauss.n_observations}, Exceedances={res_gauss.n_exceedances} ({res_gauss.observed_exceedance_rate * 100:.2f}%), Kupiec p={res_gauss.p_value:.4f}"
    )

    # 2. Heavy-tailed Student-t VaR Backtest
    res_t = run_student_t_var_backtest(series_usd_eur, alpha=0.05, window=180, df=4.0)
    print(
        f"Student-t VaR 95%: Obs={res_t['n_obs']}, Exceedances={res_t['n_exceedances']} ({res_t['rate'] * 100:.2f}%), Kupiec p={res_t['kupiec_pval']:.4f}"
    )

    print("[SUCCESS] Empirical backtesting executed cleanly.")


if __name__ == "__main__":
    main()
