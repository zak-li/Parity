"""Generate complex benchmark numbers and compile into publication-grade LaTeX report."""

from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import os

import Parity
from core.io.fx import build_default_fx_provider
from core.models.backtesting import backtest_expected_shortfall, backtest_parametric_var
from core.models.instruments import garman_kohlhagen_greeks
from core.models.ladder import CashflowTranche, simulate_ladder
from core.models.stress import apply_scenarios, canonical_scenarios, reverse_stress_test

# Initialize Parity master license
MASTER_API_KEY = os.environ.get("PARITY_API_KEY", "demo-institutional-license-key")
Parity.init(api_key=MASTER_API_KEY)


def compute_metrics():
    print("=" * 80)
    print("COMPUTING INSTITUTIONAL AUDIT & BASEL III METRICS")
    print("=" * 80)
    provider = build_default_fx_provider()
    today = dt.date.today()

    # 1. Complex Multi-Tranche Ladder Simulation (USD/EUR)
    tranches = [
        CashflowTranche("Tranche 1 - Titanium Deposit", 30, 1250000.0),
        CashflowTranche("Tranche 2 - Seattle Avionics", 60, 2500000.0),
        CashflowTranche("Tranche 3 - Chicago Sub-Assembly", 90, 3200000.0),
        CashflowTranche("Tranche 4 - Final Delivery", 180, 1800000.0),
    ]

    lookback_start = today - dt.timedelta(days=365)
    history_usd = provider.get_historical_series("USD", "EUR", lookback_start, today)
    spot_usd = float(history_usd.iloc[-1])

    ladder_res = simulate_ladder(
        tranches,
        spot=spot_usd,
        sigma_annual=0.062,
        domestic_rate=0.021,
        foreign_rate=0.043,
        target_margin_pct=0.185,
        n_sims=50000,
        seed=42,
    )

    print(f"Total Portfolio: {ladder_res.total_amount_foreign:,.2f} USD")
    print(f"Spot Rate S0: {spot_usd:.4f}")
    print(f"Unhedged Expected Margin: {ladder_res.unhedged_expected_margin_pct * 100:.2f}%")
    print(f"Unhedged Worst Case (CVaR 5%): {ladder_res.unhedged_cvar_margin_pct * 100:.2f}%")
    print(f"Layered Forward Locked Margin: {ladder_res.layered_hedged_margin_pct * 100:.2f}%")
    print(f"CVaR Protection Gain: {ladder_res.cvar_improvement_pct * 100:.2f}%")

    # 2. Garman-Kohlhagen Option Greeks Matrix
    tau_tranche3 = 90.0 / 365.0
    fwd_tranche3 = spot_usd * math.exp((0.021 - 0.043) * tau_tranche3)
    k_tranche3 = fwd_tranche3
    call_greeks = garman_kohlhagen_greeks(
        spot_usd, k_tranche3, 0.021, 0.043, 0.062, tau_tranche3, "call"
    )
    put_greeks = garman_kohlhagen_greeks(
        spot_usd, k_tranche3, 0.021, 0.043, 0.062, tau_tranche3, "put"
    )

    print(
        f"\nGarman-Kohlhagen Greeks for 90d Tranche 3 (Spot={spot_usd:.4f}, Strike={k_tranche3:.4f}):"
    )
    print(
        f"  Call Delta={call_greeks.delta:.4f} | Gamma={call_greeks.gamma:.4f} | Vega={call_greeks.vega:.4f} | Theta={call_greeks.theta:.4f}"
    )
    print(
        f"  Put  Delta={put_greeks.delta:.4f} | Gamma={put_greeks.gamma:.4f} | Vega={put_greeks.vega:.4f} | Theta={put_greeks.theta:.4f}"
    )

    # 3. Basel III Backtesting on Historical ECB Rates
    lookback_bce = today - dt.timedelta(days=550)
    series_eur_usd = provider.get_historical_series("EUR", "USD", lookback_bce, today)
    series_usd_eur = 1.0 / series_eur_usd

    bt_var = backtest_parametric_var(series_usd_eur, alpha=0.05, window=180)
    bt_es = backtest_expected_shortfall(series_usd_eur, alpha=0.05, window=180, n_scenarios=2000)

    print("\nBasel III Regulatory Backtesting Results:")
    print(f"  Evaluated Days: {bt_var.n_observations}")
    print(
        f"  Observed Exceedances: {bt_var.n_exceedances} ({bt_var.observed_exceedance_rate * 100:.2f}%)"
    )
    print(f"  Kupiec POF LR Stat: {bt_var.likelihood_ratio:.4f} | p-value: {bt_var.p_value:.4f}")
    print(f"  Acerbi-Szekely ES Stat (Z2): {bt_es.z2_statistic:.4f} | p-value: {bt_es.p_value:.4f}")

    # 4. Stress Testing & Reverse Stress Testing
    revenue_domestic = ladder_res.total_revenue_domestic
    amount_foreign = ladder_res.total_amount_foreign
    budgeted_margin = 0.185
    stress_results = apply_scenarios(
        revenue_domestic, amount_foreign, spot_usd, budgeted_margin, canonical_scenarios()
    )
    rev_stress = reverse_stress_test(
        revenue_domestic, amount_foreign, spot_usd, target_margin_pct=0.05
    )

    print("\nStress Testing & Crisis Scenarios:")
    for s in stress_results:
        print(
            f"  {s.scenario:<25}: Shock={s.rate_shock_pct * 100:+5.1f}% | Simulated Rate={s.shocked_rate:.4f} | Remaining Margin={s.margin_pct * 100:.2f}% | Margin Impact={s.margin_pct_change * 100:+.2f}%"
        )
    print(
        f"\nReverse Stress Breaking Rate (Floor 5%): S*={rev_stress.breaking_rate:.4f} (Required Move={rev_stress.required_rate_move_pct * 100:+.2f}%)"
    )


if __name__ == "__main__":
    compute_metrics()
