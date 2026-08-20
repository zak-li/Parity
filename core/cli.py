from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Sequence

from core import __version__
from core.app.risk_engine import MarginRiskEngine
from core.models.models import OrderInput


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Parity",
        description="Parity: Institutional FX risk and decision engine CLI",
    )
    parser.add_argument("--version", "-v", action="version", version=f"Parity {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # Command: simulate
    sim_parser = subparsers.add_parser(
        "simulate", aliases=["sim"], help="Run a currency risk simulation for an order"
    )
    sim_parser.add_argument(
        "--amount", "-a", type=float, required=True, help="Amount in foreign currency"
    )
    sim_parser.add_argument(
        "--foreign", "-f", type=str, required=True, help="Foreign currency code (e.g. USD)"
    )
    sim_parser.add_argument(
        "--domestic", "-d", type=str, default="EUR", help="Domestic currency code (default: EUR)"
    )
    sim_parser.add_argument(
        "--delivery", "-t", type=str, required=True, help="Delivery date (YYYY-MM-DD)"
    )
    sim_parser.add_argument(
        "--target-margin",
        "-m",
        type=float,
        default=0.15,
        help="Target profit margin (default: 0.15)",
    )
    sim_parser.add_argument(
        "--simulations", "-n", type=int, default=10000, help="Number of Monte Carlo paths"
    )
    sim_parser.add_argument("--json", "-j", action="store_true", help="Output result as raw JSON")

    # Command: health
    subparsers.add_parser("health", help="Check system environment and runtime configuration")

    return parser


def run_simulate(args: argparse.Namespace) -> int:
    try:
        delivery_date = dt.date.fromisoformat(args.delivery)
    except ValueError:
        sys.stderr.write(
            f"Error: invalid delivery date format {args.delivery!r}, expected YYYY-MM-DD\n"
        )
        return 1

    order = OrderInput(
        amount_foreign=args.amount,
        foreign_currency=args.foreign.upper(),
        domestic_currency=args.domestic.upper(),
        order_date=dt.date.today(),
        delivery_date=delivery_date,
        target_margin_pct=args.target_margin,
        n_simulations=args.simulations,
    )

    try:
        engine = MarginRiskEngine()
        result = engine.run(order)
    except Exception as exc:
        sys.stderr.write(f"Simulation failed: {exc}\n")
        return 1

    if args.json:
        out = {
            "vulnerability_score": result.vulnerability_score,
            "risk_level": result.risk_level.value,
            "expected_terminal_rate": round(float(result.expected_terminal_rate), 4),
            "probability_margin_below_threshold": round(
                float(result.probability_margin_below_threshold), 4
            ),
            "expected_shortfall_margin_pct": round(float(result.expected_shortfall_margin_pct), 4),
            "optimal_hedge_ratio": result.hedge.optimal_hedge_ratio,
            "hedged_margin_pct": round(float(result.hedge.hedged_margin_pct), 4),
        }
        print(json.dumps(out, indent=2))
        return 0

    print("\n=== Parity Currency Risk Analysis ===")
    print(
        f" Order: {args.amount:,.2f} {args.foreign.upper()} -> {args.domestic.upper()} (Delivery: {args.delivery})"
    )
    print(
        f" Vulnerability Score: {result.vulnerability_score}/100 [{result.risk_level.value.upper()}]"
    )
    print(f" Expected Terminal Rate: {result.expected_terminal_rate:.4f}")
    print(f" Loss Probability: {result.probability_margin_below_threshold * 100:.1f}%")
    print(f" Expected Shortfall (CVaR): {result.expected_shortfall_margin_pct * 100:.1f}%")
    print(f" Recommended Hedge Ratio: {result.hedge.optimal_hedge_ratio * 100:.0f}%")
    print(f" Hedged Expected Margin: {result.hedge.hedged_margin_pct * 100:.1f}%\n")
    return 0


def run_health() -> int:
    print(f"Parity v{__version__} environment: OK")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in ("simulate", "sim"):
        return run_simulate(args)
    elif args.command == "health":
        return run_health()
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
