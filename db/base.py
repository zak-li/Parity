from __future__ import annotations

from typing import Protocol, runtime_checkable

from .records import ApiAuditLogRecord, ApiKeyRecord, JobRunRecord, SimulationRecord


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


@runtime_checkable
class AuthRepository(Protocol):
    def get_api_key(self, hashed_key: str) -> ApiKeyRecord | None: ...

    def save_api_key(self, record: ApiKeyRecord) -> ApiKeyRecord: ...

    def revoke_api_key(self, key_id: str) -> bool: ...

    def log_audit(self, record: ApiAuditLogRecord) -> None: ...


@runtime_checkable
class JobRepository(Protocol):
    def save(self, record: JobRunRecord) -> JobRunRecord: ...

    def get(self, job_id: str) -> JobRunRecord | None: ...

    def update_status(
        self, job_id: str, status: str, result_id: str | None = None, error: str | None = None
    ) -> JobRunRecord | None: ...
