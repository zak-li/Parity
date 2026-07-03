from __future__ import annotations

from typing import Protocol, runtime_checkable

from .records import SimulationRecord


@runtime_checkable
class SimulationRepository(Protocol):
    def save(self, record: SimulationRecord) -> SimulationRecord: ...

    def get(self, record_id: str) -> SimulationRecord | None: ...

    def latest_for_pair(
        self, foreign_currency: str, domestic_currency: str
    ) -> SimulationRecord | None: ...

    def history(
        self,
        foreign_currency: str | None = None,
        domestic_currency: str | None = None,
        limit: int = 50,
    ) -> list[SimulationRecord]: ...

    def close(self) -> None: ...
