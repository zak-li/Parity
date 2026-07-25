from __future__ import annotations

import contextlib
import logging
from typing import Protocol

from .base import SimulationRepository
from .records import SimulationRecord

logger = logging.getLogger(__name__)


class SimulationSink(Protocol):
    def save(self, record: SimulationRecord) -> SimulationRecord: ...

    def close(self) -> None: ...


class CompositeSimulationRepository:
    def __init__(
        self, primary: SimulationRepository, secondaries: list[SimulationSink] | None = None
    ) -> None:
        self._primary = primary
        self._secondaries = secondaries or []

    def save(self, record: SimulationRecord) -> SimulationRecord:
        saved = self._primary.save(record)
        for sink in self._secondaries:
            try:
                sink.save(record)
            except Exception as exc:
                logger.warning(
                    "secondary_persistence_failed",
                    extra={"sink": type(sink).__name__, "error": str(exc)},
                )
        return saved

    def get(self, record_id: str, client_id: str | None = None) -> SimulationRecord | None:
        return self._primary.get(record_id, client_id)

    def latest_for_pair(
        self, foreign_currency: str, domestic_currency: str, client_id: str | None = None
    ) -> SimulationRecord | None:
        return self._primary.latest_for_pair(foreign_currency, domestic_currency, client_id)

    def history(
        self,
        foreign_currency: str | None = None,
        domestic_currency: str | None = None,
        limit: int = 50,
        client_id: str | None = None,
    ) -> list[SimulationRecord]:
        return self._primary.history(foreign_currency, domestic_currency, limit, client_id)

    def exposure_summary(self) -> list[dict]:
        for sink in self._secondaries:
            summary = getattr(sink, "exposure_summary", None)
            if callable(summary):
                try:
                    return summary()
                except Exception as exc:
                    logger.warning("exposure_summary_failed", extra={"error": str(exc)})
        return []

    def close(self) -> None:
        self._primary.close()
        for sink in self._secondaries:
            with contextlib.suppress(Exception):
                sink.close()
