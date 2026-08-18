from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
        target_margins = [0.05, 0.08, 0.10]
    if horizons is None:
        horizons = [30, 60, 90]
    records = []

    for h in horizons:
        # Sample non-overlapping trade entry points every h business days
        sampled_series = series.iloc[::h]
        # Calculate h-day log returns on non-overlapping steps
        h_returns = np.log(sampled_series.shift(-1) / sampled_series).dropna()

        for alpha in alphas:
            # Estimate 120-day annualized rolling volatility projected to h days
            rolling_std = series.pct_change().rolling(120).std().loc[h_returns.index] * np.sqrt(h)
            gauss_var = norm.ppf(1 - alpha) * rolling_std

            common_idx = h_returns.index.intersection(gauss_var.dropna().index)
            rets = h_returns.loc[common_idx]
            vars_g = gauss_var.loc[common_idx]

            for target in target_margins:
                # Importer loss occurs when currency appreciates against domestic (rets > target)
                deemed_safe_by_gaussian = vars_g <= target
                actual_loss_exceeded_target = rets > target

                missed_hedges = int((deemed_safe_by_gaussian & actual_loss_exceeded_target).sum())
                total_trades = len(common_idx)
                missed_rate = missed_hedges / total_trades if total_trades > 0 else 0.0

                records.append(
                    {
                        "Horizon_Days": h,
                        "Alpha": alpha,
                        "Target_Margin": target,
                        "Total_Trades": total_trades,
                        "Missed_Hedges": missed_hedges,
                        "Unhedged_Loss_Rate": missed_rate * 100.0,
                    }
                )

    return pd.DataFrame(records)


def main():
    provider = FrankfurterFxDataProvider()
    start, end = dt.date(2017, 1, 1), dt.date(2023, 12, 31)

    print("=========================================================================")
    print("EUR/MAD vs USD/MAD NON-OVERLAPPING P&L & REGIME BENCHMARK")
    print("=========================================================================\n")

    usd_mad = provider.get_historical_series("USD", "MAD", start, end)
    eur_mad = provider.get_historical_series("EUR", "MAD", start, end)

    print(f"Loaded USD/MAD ({len(usd_mad)} obs) and EUR/MAD ({len(eur_mad)} obs)")

    print("\n--- 1. REGIME CONTRAST: EUR/MAD (60% Basket Weight) vs USD/MAD (40% Weight) ---")
    for pair_name, s in [
        ("EUR/MAD (Basket Anchor 60%)", eur_mad),
        ("USD/MAD (Basket Component 40%)", usd_mad),
    ]:
        rets = np.log(s / s.shift(1)).dropna()
        rolling = rets.rolling(60)
        thresh = (rolling.mean() + norm.ppf(0.05) * rolling.std(ddof=1)).shift(1)
        valid = thresh.notna()
        ind = (rets[valid] < thresh[valid]).astype(int)

        kup = kupiec_pof_test(len(ind), int(ind.sum()), 0.05)
        chr_test = christoffersen_independence_test(ind.to_numpy())

        print(f"\n[{pair_name}] (N={len(ind)})")
        print(f" Realized Exceedances: {ind.sum()} ({ind.sum() / len(ind) * 100:.2f}%)")
        print(f" Kupiec p-val: {kup.p_value:.4f} (Rej={kup.rejected})")
        print(f" Christoffersen Ind p-val: {chr_test.p_value:.4f} (Rej={chr_test.rejected})")

    print("\n--- 2. NON-OVERLAPPING IMPORTER P&L LOSS SURFACE (USD/MAD) ---")
    usd_pnl = evaluate_non_overlapping_pnl_surface(usd_mad)
    pivot_usd = usd_pnl.pivot_table(
        index=["Horizon_Days", "Alpha"],
        columns="Target_Margin",
        values=["Total_Trades", "Missed_Hedges", "Unhedged_Loss_Rate"],
    )
    print("\nUSD/MAD Non-Overlapping P&L Surface:")
    print(pivot_usd.to_string(float_format=lambda x: f"{x:.2f}"))

    print("\n--- 3. NON-OVERLAPPING IMPORTER P&L LOSS SURFACE (EUR/MAD) ---")
    eur_pnl = evaluate_non_overlapping_pnl_surface(eur_mad)
    pivot_eur = eur_pnl.pivot_table(
        index=["Horizon_Days", "Alpha"],
        columns="Target_Margin",
        values=["Total_Trades", "Missed_Hedges", "Unhedged_Loss_Rate"],
    )
    print("\nEUR/MAD Non-Overlapping P&L Surface:")
    print(pivot_eur.to_string(float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()
