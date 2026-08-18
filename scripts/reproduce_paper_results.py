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
    christoffersen_independence_test,
    kupiec_pof_test,
)


def fit_in_sample_df(series: pd.Series) -> float:
    """Fit Student-t degrees of freedom on in-sample returns strictly."""
    returns = np.log(series / series.shift(1)).dropna().to_numpy()
    params = student_t.fit(returns)
    df_fit = float(params[0])
    return max(min(df_fit, 10.0), 2.5)


def run_strict_out_of_sample_backtest(
    full_series: pd.Series,
    split_date: pd.Timestamp,
    alpha: float,
    window: int = 60,
    model_type: str = "gaussian",
    df: float = 4.0,
) -> dict:
    """Run rolling backtest where threshold uses preceding window, but evaluation is STRICTLY out-of-sample (t >= split_date)."""
    returns = np.log(full_series / full_series.shift(1)).dropna()
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

    # STRICT Out-of-Sample filtering: evaluation days must be >= split_date
    out_mask = (returns.index >= split_date) & threshold.notna()
    realized_ret = returns[out_mask]
    thresh_val = threshold[out_mask]

    exceedances_indicator = (realized_ret < thresh_val).astype(int)
    n_obs = len(exceedances_indicator)
    n_exceedances = int(exceedances_indicator.sum())

    kupiec = kupiec_pof_test(n_obs, n_exceedances, alpha)
    christoffersen = christoffersen_independence_test(exceedances_indicator.to_numpy())

    return {
        "n_obs": n_obs,
        "n_exceedances": n_exceedances,
        "exceedance_rate": n_exceedances / n_obs if n_obs > 0 else 0.0,
        "kupiec_lr": kupiec.likelihood_ratio,
        "kupiec_pval": kupiec.p_value,
        "kupiec_rej": kupiec.rejected,
        "christ_lr": christoffersen.likelihood_ratio,
        "christ_pval": christoffersen.p_value,
        "christ_rej": christoffersen.rejected,
    }


def main():
    provider = FrankfurterFxDataProvider()
    start, end = dt.date(2017, 1, 1), dt.date(2023, 12, 31)

    print("=========================================================================")
    print("PARITY (`Xi`) CANONICAL PAPER REPRODUCIBILITY BENCHMARK")
    print("=========================================================================\n")

    usd_mad = provider.get_historical_series("USD", "MAD", start, end)
    eur_mad = provider.get_historical_series("EUR", "MAD", start, end)

    print(
        f"USD/MAD total observations: {len(usd_mad)} ({usd_mad.index[0].date()} to {usd_mad.index[-1].date()})"
    )
    print(
        f"EUR/MAD total observations: {len(eur_mad)} ({eur_mad.index[0].date()} to {eur_mad.index[-1].date()})"
    )

    # 1. Strict In-Sample vs Out-of-Sample Split
    in_sample_end = pd.Timestamp("2019-12-31")
    out_sample_start = pd.Timestamp("2020-01-01")

    in_sample_usd = usd_mad.loc[:in_sample_end]
    df_calibrated = fit_in_sample_df(in_sample_usd)
    print(
        f"\n1. In-Sample Fitting (USD/MAD 2018-2019, N={len(in_sample_usd)}): Calibrated Student-t df* = {df_calibrated:.2f}"
    )

    print(
        "\n2. STRICT Out-of-Sample Evaluation (USD/MAD 2020 COVID Shock, t >= 2020-01-01, Window=60):"
    )
    window = 60
    for alpha in [0.05, 0.01]:
        print(f"\n   [Quantile Alpha = {alpha * 100:.1f}%]")

        # Gaussian Normal
        g_res = run_strict_out_of_sample_backtest(
            usd_mad, split_date=out_sample_start, alpha=alpha, window=window, model_type="gaussian"
        )
        print(
            f"   Gaussian Normal VaR:  N={g_res['n_obs']}, Exceed={g_res['n_exceedances']} ({g_res['exceedance_rate'] * 100:.2f}%), "
            f"Kupiec p={g_res['kupiec_pval']:.4f} (Rej={g_res['kupiec_rej']}), "
            f"Christoffersen p={g_res['christ_pval']:.4f} (Rej={g_res['christ_rej']})"
        )

        # Calibrated Student-t
        t_res = run_strict_out_of_sample_backtest(
            usd_mad,
            split_date=out_sample_start,
            alpha=alpha,
            window=window,
            model_type="student_t",
            df=df_calibrated,
        )
        print(
            f"   Calibrated Student-t: N={t_res['n_obs']}, Exceed={t_res['n_exceedances']} ({t_res['exceedance_rate'] * 100:.2f}%), "
            f"Kupiec p={t_res['kupiec_pval']:.4f} (Rej={t_res['kupiec_rej']}), "
            f"Christoffersen p={t_res['christ_pval']:.4f} (Rej={t_res['christ_rej']})"
        )

    print("\n3. Full-Sample Basket Contrast (2016-2020, N=919 rolling observations):")
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

        print(f"\n   [{pair_name}]")
        print(
            f"   Obs N={len(ind)}, Exceed={ind.sum()} ({ind.sum() / len(ind) * 100:.2f}%), "
            f"Kupiec p={kup.p_value:.4f}, Christoffersen p={chr_test.p_value:.4f} (Rej={chr_test.rejected})"
        )


if __name__ == "__main__":
    main()
