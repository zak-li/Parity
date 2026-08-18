from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

from core.io.fx.frankfurter import FrankfurterFxDataProvider
from core.models.backtesting import (
    backtest_expected_shortfall,
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
    # Var(t_df) = df / (df - 2); scale factor = sqrt((df - 2) / df)
    scale_factor = np.sqrt((df - 2.0) / df)
    t_quant = student_t.ppf(alpha, df=df) * scale_factor

    rolling = returns.rolling(window)
    threshold = (rolling.mean() + t_quant * rolling.std(ddof=1)).shift(1)
    valid = threshold.notna()
    exceedances = int((returns[valid] < threshold[valid]).sum())
    n_obs = int(valid.sum())

    kupiec = kupiec_pof_test(n_obs, exceedances, alpha)
    return {
        "n_obs": n_obs,
        "exceedances": exceedances,
        "expected": n_obs * alpha,
        "rate": exceedances / n_obs,
        "lr": kupiec.likelihood_ratio,
        "p_value": kupiec.p_value,
        "rejected": kupiec.rejected,
    }


def main():
    provider = FrankfurterFxDataProvider()
    start = dt.date(2020, 1, 1)
    end = dt.date(2023, 12, 31)

    pairs = [("EUR", "USD"), ("USD", "MAD")]
    alphas = [0.05, 0.01]
    window = 252

    print("=========================================================================")
    print("PARITY (`Xi`) EMPIRICAL BACKTEST BENCHMARK REPORT")
    print("=========================================================================\n")

    for base, quote in pairs:
        pair_str = f"{base}/{quote}"
        pair_start = dt.date(2018, 1, 1) if quote == "MAD" else start
        print(
            f"--- Dataset: {pair_str} ({pair_start.isoformat()} to {end.isoformat()}, 1-Year Rolling Window = 252) ---"
        )
        try:
            series = provider.get_historical_series(base, quote, pair_start, end)
        except Exception as e:
            print(f"Failed to fetch {pair_str}: {e}")
            continue

        for alpha in alphas:
            print(f"\n[Target Confidence Alpha = {alpha * 100:.1f}%]")

            # 1. Gaussian Parametric VaR
            gauss_var = backtest_parametric_var(series, alpha=alpha, window=window)
            print(
                f" Gaussian VaR:      Obs={gauss_var.n_observations}, Target={gauss_var.n_observations * alpha:.1f}, "
                f"Realized={gauss_var.n_exceedances} ({gauss_var.observed_exceedance_rate * 100:.2f}%), "
                f"LR={gauss_var.likelihood_ratio:.4f}, p-val={gauss_var.p_value:.4f}, Rejected={gauss_var.rejected}"
            )

            # 2. Student-t Heavy-Tail VaR (df=4.0)
            st_var = run_student_t_var_backtest(series, alpha=alpha, window=window, df=4.0)
            print(
                f" Student-t VaR:     Obs={st_var['n_obs']}, Target={st_var['expected']:.1f}, "
                f"Realized={st_var['exceedances']} ({st_var['rate'] * 100:.2f}%), "
                f"LR={st_var['lr']:.4f}, p-val={st_var['p_value']:.4f}, Rejected={st_var['rejected']}"
            )

            # 3. Expected Shortfall (Acerbi-Székely Test 2)
            es_bt = backtest_expected_shortfall(series, alpha=alpha, window=window, seed=42)
            print(
                f" Acerbi-Székely ES: Z2={es_bt.z2_statistic:.4f}, p-val={es_bt.p_value:.4f}, Rejected={es_bt.rejected}"
            )

        print("\n" + "-" * 73 + "\n")


if __name__ == "__main__":
    main()
