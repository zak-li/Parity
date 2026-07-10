"""Regenerate the README hero chart from real engine output.

Runs a representative margin-risk simulation on live ECB/Frankfurter FX data and
plots the unhedged vs forward-hedged margin (expected value and 95% CVaR). The
numbers are produced by the engine itself, so the chart stays honest and
reproducible.

Requires matplotlib (not a runtime dependency):  pip install matplotlib
Usage:  python scripts/generate_readme_chart.py
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from core.app.risk_engine import MarginRiskEngine  # noqa: E402
from core.io.fx.frankfurter import FrankfurterFxDataProvider  # noqa: E402
from core.models.enums import HedgeInstrument  # noqa: E402
from core.models.models import OrderInput  # noqa: E402

N_SIMS = 100_000
TARGET_PCT = 15.0
OUT_DIR = Path(__file__).resolve().parents[1] / "charts"

NAVY = "#0F1B33"
BRAND_BLUE = "#3A60F0"


def compute() -> dict[str, float]:
    order = OrderInput(
        amount_foreign=200_000,
        foreign_currency="USD",
        domestic_currency="EUR",
        order_date=dt.date.today(),
        delivery_date=dt.date.today() + dt.timedelta(days=90),
        target_margin_pct=TARGET_PCT / 100,
        min_acceptable_margin_pct=0.05,
        domestic_rate=0.021,
        foreign_rate=0.043,
        n_simulations=N_SIMS,
        seed=7,
    )
    result = MarginRiskEngine(FrankfurterFxDataProvider()).run(order)
    by = {o.instrument: o for o in result.instrument_comparison}
    none, fwd = by[HedgeInstrument.NONE], by[HedgeInstrument.FORWARD]
    return {
        "unhedged_cvar": none.cvar_margin_pct * 100,
        "unhedged_ev": none.expected_margin_pct * 100,
        "hedged_cvar": fwd.cvar_margin_pct * 100,
        "hedged_ev": fwd.expected_margin_pct * 100,
    }


def render(data: dict[str, float], *, dark: bool) -> None:
    ink = "#F5F7FA" if dark else "#0F1B33"
    muted = "#9AA6BF" if dark else "#5B6472"
    surface = "#0D1117" if dark else "#FFFFFF"
    grid = "#2C3448" if dark else "#D7DCE5"

    plt.rcParams.update(
        {"font.family": "serif", "font.serif": ["Garamond", "Georgia", "DejaVu Serif"]}
    )
    fig, ax = plt.subplots(figsize=(11, 8))
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)

    cvar = [data["unhedged_cvar"], data["hedged_cvar"]]
    ev = [data["unhedged_ev"], data["hedged_ev"]]
    x = [0.0, 1.0]
    w = 0.32

    ax.bar(
        [xi - w / 2 for xi in x],
        cvar,
        w,
        color=NAVY if not dark else "#1B2A52",
        label="Worst case (95% CVaR)",
    )
    ax.bar([xi + w / 2 for xi in x], ev, w, color=BRAND_BLUE, label="Expected margin")

    for xi, c, e in zip(x, cvar, ev, strict=True):
        ax.text(
            xi - w / 2,
            c + 0.3,
            f"{c:.1f}%",
            ha="center",
            va="bottom",
            fontsize=15,
            fontweight="bold",
            color=ink,
        )
        ax.text(
            xi + w / 2,
            e + 0.3,
            f"{e:.1f}%",
            ha="center",
            va="bottom",
            fontsize=15,
            fontweight="bold",
            color=ink,
        )

    ax.axhline(TARGET_PCT, ls="--", lw=1.2, color=muted)
    ax.text(
        1.74,
        TARGET_PCT + 0.15,
        f"Target ({TARGET_PCT:.0f}%)",
        va="bottom",
        ha="right",
        fontsize=12,
        color=muted,
    )

    ax.set_xticks(x)
    ax.set_xticklabels(
        ["Without Parity\nUnhedged exposure", "With Parity\nForward hedge"], fontsize=14, color=ink
    )
    ax.set_ylim(0, TARGET_PCT + 4)
    ax.set_yticks([])
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(grid)
    ax.tick_params(length=0)
    ax.set_xlim(-0.6, 1.75)

    fig.text(
        0.06,
        0.93,
        "Predictable margins in any currency market",
        fontsize=23,
        fontweight="bold",
        color=ink,
    )
    fig.text(
        0.06,
        0.875,
        "Locking cross-border margins with Parity's data-driven hedge.",
        fontsize=13.5,
        color=muted,
    )
    ax.legend(
        loc="lower center",
        ncol=2,
        frameon=False,
        fontsize=12.5,
        bbox_to_anchor=(0.5, 1.005),
        labelcolor=ink,
    )

    fig.text(
        0.06,
        0.02,
        f"Note: {N_SIMS:,} Monte Carlo paths on live ECB/Frankfurter FX data (USD/EUR), risk-neutral GBM. "
        f"Figures are engine output.\nSource: Parity engine",
        fontsize=10.5,
        color=muted,
        ha="left",
    )

    fig.subplots_adjust(bottom=0.16, top=0.70, left=0.06, right=0.97)
    suffix = "dark" if dark else "light"
    OUT_DIR.mkdir(exist_ok=True)
    fig.savefig(OUT_DIR / f"parity_before_after_{suffix}.png", dpi=300, facecolor=surface)
    plt.close(fig)


def main() -> None:
    data = compute()
    render(data, dark=False)
    render(data, dark=True)
    print(
        "Generated charts/parity_before_after_{light,dark}.png from:",
        {k: round(v, 2) for k, v in data.items()},
    )


if __name__ == "__main__":
    main()
