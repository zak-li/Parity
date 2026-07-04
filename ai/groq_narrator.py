from __future__ import annotations

import logging
import os
from typing import Protocol

from core.models.models import SimulationResult

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a currency-risk management advisor for importing SMEs. "
    "From the indicators provided, write a clear, actionable explanation in "
    "English (3 to 5 sentences), without unnecessary jargon. Do not invent any "
    "figures: use only the data provided. End with one concrete recommendation."
)


class Narrator(Protocol):
    def narrate(self, result: SimulationResult) -> str | None: ...


class NullNarrator:
    def narrate(self, result: SimulationResult) -> str | None:
        return None


def _build_prompt(result: SimulationResult) -> str:
    order = result.order
    return (
        f"Pair: {order.foreign_currency}/{order.domestic_currency}. "
        f"Amount: {order.amount_foreign:.0f} {order.foreign_currency}. "
        f"Horizon: {result.horizon_days} days. "
        f"Spot rate: {result.spot_rate_order_date:.4f}, "
        f"theoretical forward rate: {result.expected_terminal_rate:.4f}. "
        f"Annualized volatility: {result.annualized_volatility * 100:.1f}%. "
        f"Vulnerability score: {result.vulnerability_score}/100 ({result.risk_level.value}). "
        f"Probability of insufficient margin: {result.probability_margin_below_threshold * 100:.0f}%. "
        f"Average loss in the worst cases (CVaR): {result.expected_shortfall_margin_pct * 100:.1f}%. "
        f"Recommended optimal hedge: {result.hedge.optimal_hedge_ratio * 100:.0f}% "
        f"(margin locked at {result.hedge.hedged_margin_pct * 100:.1f}%)."
    )


class GroqNarrator:
    def __init__(
        self, api_key: str, model: str = "llama-3.3-70b-versatile", timeout: float = 20.0
    ) -> None:
        from groq import Groq

        self._client = Groq(api_key=api_key, timeout=timeout)
        self._model = model

    def narrate(self, result: SimulationResult) -> str | None:
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _build_prompt(result)},
                ],
                temperature=0.3,
                max_tokens=400,
            )
            return completion.choices[0].message.content
        except Exception as exc:
            logger.warning("groq_narrative_failed", extra={"error": str(exc)})
            return None


def build_narrator() -> Narrator:
    api_key = os.environ.get("XI_GROQ_API_KEY")
    if not api_key:
        return NullNarrator()
    model = os.environ.get("XI_GROQ_MODEL", "llama-3.3-70b-versatile")
    try:
        return GroqNarrator(api_key=api_key, model=model)
    except Exception as exc:
        logger.warning("groq_unavailable", extra={"error": str(exc)})
        return NullNarrator()
