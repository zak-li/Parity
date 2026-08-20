from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from scipy.stats import norm

from core.io.fx.frankfurter import FrankfurterFxDataProvider
from core.models.backtesting import (
    christoffersen_independence_test,
    kupiec_pof_test,
)


def evaluate_non_overlapping_pnl_surface(
    series: pd.Series,
    alphas: list[float] | None = None,
    target_margins: list[float] | None = None,
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    """Evaluate P&L impact surface on NON-OVERLAPPING trades (sampling every h business days)."""
    if alphas is None:
        alphas = [0.05, 0.01]
    if target_margins is None:
        target_margins = [0.05, 0.10, 0.15]
    if horizons is None:
        horizons = [21, 63, 126]  # 1M, 3M, 6M

    results = []

    for h in horizons:
        sampled_dates = series.index[::h]
        sampled_prices = series.loc[sampled_dates]

        h_returns = (sampled_prices / sampled_prices.shift(1)) - 1.0
        h_returns = h_returns.dropna()

        N = len(h_returns)
        if N < 15:
            continue

        sigma_annual = h_returns.std() * np.sqrt(252.0 / h)
        dt_horizon = h / 252.0

        for alpha in alphas:
            z = norm.ppf(1.0 - alpha)
            var_pct = z * sigma_annual * np.sqrt(dt_horizon)

            exceptions = int((h_returns > var_pct).sum())
            actual_rate = exceptions / N if N > 0 else 0.0

            pof_res = kupiec_pof_test(N, exceptions, alpha)
            hits_bool = (h_returns > var_pct).astype(int).tolist()
            ind_res = christoffersen_independence_test(hits_bool)

            for tm in target_margins:
                unhedged_final_margins = tm - h_returns
                unhedged_mean_margin = float(unhedged_final_margins.mean())
                unhedged_worst_margin = float(unhedged_final_margins.min())

                shortfall_condition = unhedged_final_margins[
                    unhedged_final_margins < (tm - var_pct)
                ]
                unhedged_es = (
                    float(shortfall_condition.mean())
                    if len(shortfall_condition) > 0
                    else unhedged_worst_margin
                )

                forward_margin = tm
                cvar_protection_gain = forward_margin - unhedged_es

                results.append(
                    {
                        "Horizon_Days": h,
                        "N_Trades": N,
                        "Alpha": alpha,
                        "Target_Margin": tm,
                        "Unhedged_Mean_Margin": unhedged_mean_margin,
                        "Unhedged_Worst_Margin": unhedged_worst_margin,
                        "Unhedged_ES": unhedged_es,
                        "Forward_Locked_Margin": forward_margin,
                        "Margin_Protection_Gain": cvar_protection_gain,
                        "VaR_Exceptions": exceptions,
                        "VaR_Actual_Rate": actual_rate,
                        "Kupiec_LR": pof_res.likelihood_ratio,
                        "Kupiec_p": pof_res.p_value,
                        "Christoffersen_p": ind_res.p_value,
                    }
                )

    return pd.DataFrame(results)


def main():
    print("=" * 80)
    print("BENCHMARK P&L & INSTITUTIONAL RISK ATTRIBUTION")
    print("=" * 80)
    provider = FrankfurterFxDataProvider()
    start_date = dt.date(2021, 1, 1)
    end_date = dt.date(2026, 2, 1)

    series_eur_usd = provider.get_historical_series("EUR", "USD", start_date, end_date)
    series_usd_eur = 1.0 / series_eur_usd

    df_pnl = evaluate_non_overlapping_pnl_surface(series_usd_eur)
    print(f"\nSurface calculated across {len(df_pnl)} institutional scenarios.")
    print(
        df_pnl[
            [
                "Horizon_Days",
                "Alpha",
                "Target_Margin",
                "Unhedged_Worst_Margin",
                "Forward_Locked_Margin",
                "Margin_Protection_Gain",
                "Kupiec_p",
            ]
        ].head(10)
    )
    print("\n[SUCCESS] Institutional PnL surface benchmark executed cleanly.")


if __name__ == "__main__":
    main()
