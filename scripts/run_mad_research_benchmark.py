from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.stats import t as student_t

from core.io.fx.frankfurter import FrankfurterFxDataProvider
from core.models.backtesting import (
    backtest_expected_shortfall,
    christoffersen_independence_test,
    kupiec_pof_test,
)


def run_full_model_backtest(
    series: pd.Series, alpha: float, window: int, model_type: str = "gaussian", df: float = 4.0
) -> dict:
    """Run full backtest suite: Kupiec POF, Christoffersen Independence, and Exceedance rate."""
    returns = np.log(series / series.shift(1)).dropna()
    if len(returns) <= window:
        raise ValueError("Series too short for window")

    rolling = returns.rolling(window)
    if model_type == "gaussian":
        z = norm.ppf(alpha)
        threshold = (rolling.mean() + z * rolling.std(ddof=1)).shift(1)
    elif model_type == "student_t":
        scale_factor = np.sqrt((df - 2.0) / df)
        t_quant = student_t.ppf(alpha, df=df) * scale_factor
        threshold = (rolling.mean() + t_quant * rolling.std(ddof=1)).shift(1)
    else:
        raise ValueError(f"Unknown model_type: {model_type}")

    valid = threshold.notna()
    realized_ret = returns[valid].to_numpy()
    thresh_val = threshold[valid].to_numpy()

    exceedances_indicator = (realized_ret < thresh_val).astype(int)
    n_obs = len(exceedances_indicator)
    n_exceedances = int(exceedances_indicator.sum())

    kupiec = kupiec_pof_test(n_obs, n_exceedances, alpha)
    christoffersen = christoffersen_independence_test(exceedances_indicator)

    return {
        "n_obs": n_obs,
        "n_exceedances": n_exceedances,
        "expected": n_obs * alpha,
        "rate": n_exceedances / n_obs,
        "kupiec_lr": kupiec.likelihood_ratio,
        "kupiec_pval": kupiec.p_value,
        "kupiec_rej": kupiec.rejected,
        "christ_lr": christoffersen.likelihood_ratio,
        "christ_pval": christoffersen.p_value,
        "christ_rej": christoffersen.rejected,
        "exceedances_indicator": exceedances_indicator,
    }


def fit_in_sample_df(series: pd.Series) -> float:
    """Fit Student-t degrees of freedom on in-sample returns."""
    returns = np.log(series / series.shift(1)).dropna().to_numpy()
    params = student_t.fit(returns)
    df_fit = float(params[0])
    return max(min(df_fit, 10.0), 2.5)  # Constrain between 2.5 and 10.0


def main():
    provider = FrankfurterFxDataProvider()

    # Full data range: 2018-01-01 to 2023-12-31
    in_start = dt.date(2018, 1, 1)
    out_end = dt.date(2023, 12, 31)

    print("=========================================================================")
    print("USD/MAD MANAGED-FLOAT FX TAIL RISK & MODEL SELECTION RESEARCH BENCHMARK")
    print("=========================================================================\n")

    print("Fetching USD/MAD full series (2018-01-01 to 2023-12-31)...")
    full_series = provider.get_historical_series("USD", "MAD", in_start, out_end)
    print(
        f"Full series length: {len(full_series)} (from {full_series.index[0].date()} to {full_series.index[-1].date()})"
    )

    # In-sample period: 2018-01-01 to 2019-12-31
    # Out-of-sample period: 2020-01-01 to 2020-10-30 (COVID-19 shock)
    in_series = full_series.loc[: pd.Timestamp("2019-12-31")]
    out_series = full_series.loc[pd.Timestamp("2019-09-01") :]

    df_calibrated = fit_in_sample_df(in_series)
    print(f"In-Sample Calibrated Student-t df (2018-2019): {df_calibrated:.2f}")

    window = 60  # ~3-month rolling window for out-of-sample backtest
    alphas = [0.05, 0.01]

    print("\n--- OUT-OF-SAMPLE BACKTEST RESULTS (USD/MAD 2020 COVID Shock, Window=60) ---")

    for alpha in alphas:
        print(f"\n[Confidence Level Alpha = {alpha * 100:.1f}%]")

        # 1. Gaussian Normal Model
        g_res = run_full_model_backtest(
            out_series, alpha=alpha, window=window, model_type="gaussian"
        )
        print(
            f" Gaussian Normal VaR:  Exceed={g_res['n_exceedances']}/{g_res['n_obs']} ({g_res['rate'] * 100:.2f}%), "
            f"Kupiec p={g_res['kupiec_pval']:.4f} (Rej={g_res['kupiec_rej']}), "
            f"Christoffersen Ind p={g_res['christ_pval']:.4f} (Rej={g_res['christ_rej']})"
        )

        # 2. Out-of-Sample Calibrated Student-t Model
        t_res = run_full_model_backtest(
            out_series, alpha=alpha, window=window, model_type="student_t", df=df_calibrated
        )
        print(
            f" Calibrated Student-t: Exceed={t_res['n_exceedances']}/{t_res['n_obs']} ({t_res['rate'] * 100:.2f}%), "
            f"Kupiec p={t_res['kupiec_pval']:.4f} (Rej={t_res['kupiec_rej']}), "
            f"Christoffersen Ind p={t_res['christ_pval']:.4f} (Rej={t_res['christ_rej']})"
        )

        # 3. Acerbi-Szekely Expected Shortfall Test 2
        es_res = backtest_expected_shortfall(out_series, alpha=alpha, window=window, seed=42)
        print(
            f" Acerbi-Székely ES:    Z2={es_res.z2_statistic:.4f}, ES p-val={es_res.p_value:.4f}, Rej={es_res.rejected}"
        )


if __name__ == "__main__":
    main()
