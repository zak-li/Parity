from __future__ import annotations

import threading

from .records import SimulationRecord


class InMemorySimulationRepository:
    def __init__(self) -> None:
        self._records: dict[str, SimulationRecord] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def save(self, record: SimulationRecord) -> SimulationRecord:
        with self._lock:
            self._records[record.id] = record
            self._order.append(record.id)
        return record

    def get(self, record_id: str) -> SimulationRecord | None:
        with self._lock:
            return self._records.get(record_id)

    def latest_for_pair(
        self, foreign_currency: str, domestic_currency: str
    ) -> SimulationRecord | None:
        pair = f"{foreign_currency}{domestic_currency}".upper()
        with self._lock:
            for record_id in reversed(self._order):
                record = self._records[record_id]
                if record.pair == pair:
                    return record
        return None

    def history(
        self,
        foreign_currency: str | None = None,
        domestic_currency: str | None = None,
        limit: int = 50,
    ) -> list[SimulationRecord]:
        with self._lock:
            records = [self._records[i] for i in reversed(self._order)]
        if foreign_currency:
            records = [r for r in records if r.foreign_currency == foreign_currency.upper()]
        if domestic_currency:
            records = [r for r in records if r.domestic_currency == domestic_currency.upper()]
        return records[: max(limit, 0)]

    def close(self) -> None:
        return None
