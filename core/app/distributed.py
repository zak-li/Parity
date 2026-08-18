"""Distributed batch simulation with Apache Spark — an engine capability.

Runs the :class:`~core.app.risk_engine.MarginRiskEngine` over many orders in
parallel so a whole book of exposures can be scored across a Spark cluster (or
``local[*]``). Each task simulates one order and returns a compact summary.

CLI::

    python -m core.app.distributed --input orders.json [--output out.json]

The Spark master defaults to ``$XI_SPARK_MASTER`` or ``local[*]``. On the VM
that resolves to ``spark://127.0.0.1:7077``; from a local machine, point it at
``spark://10.10.10.150:7077``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from collections.abc import Callable, Sequence
from typing import Any

from core.app.risk_engine import MarginRiskEngine
from core.io.fx import FxDataProvider, build_default_fx_provider
from core.models.models import OrderInput, SimulationResult


def _as_date(value: str | dt.date) -> dt.date:
    return dt.date.fromisoformat(value) if isinstance(value, str) else value


def order_from_dict(d: dict[str, Any]) -> OrderInput:
    return OrderInput(
        amount_foreign=float(d["amount_foreign"]),
        foreign_currency=d["foreign_currency"],
        domestic_currency=d["domestic_currency"],
        order_date=_as_date(d.get("order_date") or dt.date.today().isoformat()),
        delivery_date=_as_date(d["delivery_date"]),
        expected_revenue_domestic=d.get("expected_revenue_domestic"),
        target_margin_pct=d.get("target_margin_pct"),
        min_acceptable_margin_pct=d.get("min_acceptable_margin_pct", 0.0),
        domestic_rate=d.get("domestic_rate", 0.0),
        foreign_rate=d.get("foreign_rate", 0.0),
        n_simulations=int(d.get("n_simulations", 20_000)),
        lookback_days=int(d.get("lookback_days", 180)),
        seed=d.get("seed"),
    )


def summarize(result: SimulationResult) -> dict[str, Any]:
    order = result.order
    return {
        "pair": f"{order.foreign_currency}/{order.domestic_currency}",
        "amount_foreign": order.amount_foreign,
        "horizon_days": result.horizon_days,
        "vulnerability_score": result.vulnerability_score,
        "risk_level": result.risk_level.value,
        "budgeted_margin_pct": result.budgeted_margin_pct,
        "probability_margin_below_threshold": result.probability_margin_below_threshold,
        "expected_shortfall_margin_pct": result.expected_shortfall_margin_pct,
        "optimal_hedge_ratio": result.hedge.optimal_hedge_ratio,
        "hedged_margin_pct": result.hedge.hedged_margin_pct,
    }


def _build_provider() -> FxDataProvider:
    # Constructed inside each Spark task; patched in tests.
    return build_default_fx_provider()


def simulate_order(order_dict: dict[str, Any]) -> dict[str, Any]:
    """Simulate a single order — the function distributed across Spark tasks."""
    order = order_from_dict(order_dict)
    engine = MarginRiskEngine(fx_provider=_build_provider())
    return summarize(engine.run(order))


def resolve_master(master: str | None = None) -> str:
    """Resolve the Spark master from the argument, ``$XI_SPARK_MASTER`` or local."""
    return master or os.environ.get("XI_SPARK_MASTER", "local[*]")


def run_batch(
    orders: Sequence[dict[str, Any]],
    master: str | None = None,
    simulate_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:  # pragma: no cover - requires a running Spark/JVM
    """Distribute ``orders`` across Spark and collect per-order summaries."""
    from pyspark.sql import SparkSession

    fn = simulate_fn or simulate_order
    spark = (
        SparkSession.builder.appName("parity-batch-simulation")
        .master(resolve_master(master))
        .getOrCreate()
    )
    try:
        partitions = max(1, min(len(orders), 16))
        rdd = spark.sparkContext.parallelize(list(orders), partitions)
        return rdd.map(fn).collect()
    finally:
        spark.stop()


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - CLI entry point
    parser = argparse.ArgumentParser(
        description="Run Parity simulations in parallel on Apache Spark."
    )
    parser.add_argument("--input", required=True, help="JSON file: array of order objects.")
    parser.add_argument("--output", help="Optional path to write results as JSON.")
    parser.add_argument(
        "--master", default=None, help="Spark master (default: $XI_SPARK_MASTER or local[*])."
    )
    args = parser.parse_args(argv)

    with open(args.input, encoding="utf-8") as handle:
        orders = json.load(handle)

    results = run_batch(orders, master=args.master)
    payload = json.dumps(results, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload)
    else:
        print(payload)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
