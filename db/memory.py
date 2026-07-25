from __future__ import annotations

import datetime as dt
import threading

from .records import ApiAuditLogRecord, ApiKeyRecord, JobRunRecord, SimulationRecord


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

    def get(self, record_id: str, client_id: str | None = None) -> SimulationRecord | None:
        with self._lock:
            record = self._records.get(record_id)
        if record is None:
            return None
        if client_id is not None and record.client_id != client_id:
            return None
        return record

    def latest_for_pair(
        self, foreign_currency: str, domestic_currency: str, client_id: str | None = None
    ) -> SimulationRecord | None:
        pair = f"{foreign_currency}{domestic_currency}".upper()
        with self._lock:
            for record_id in reversed(self._order):
                record = self._records[record_id]
                if record.pair == pair and (client_id is None or record.client_id == client_id):
                    return record
        return None

    def history(
        self,
        foreign_currency: str | None = None,
        domestic_currency: str | None = None,
        limit: int = 50,
        client_id: str | None = None,
    ) -> list[SimulationRecord]:
        with self._lock:
            records = [self._records[i] for i in reversed(self._order)]
        if client_id is not None:
            records = [r for r in records if r.client_id == client_id]
        if foreign_currency:
            records = [r for r in records if r.foreign_currency == foreign_currency.upper()]
        if domestic_currency:
            records = [r for r in records if r.domestic_currency == domestic_currency.upper()]
        return records[: max(limit, 0)]

    def close(self) -> None:
        return None


class InMemoryAuthRepository:
    def __init__(self) -> None:
        self._keys: dict[str, ApiKeyRecord] = {}
        self._logs: list[ApiAuditLogRecord] = []
        self._lock = threading.Lock()

    def get_api_key(self, hashed_key: str) -> ApiKeyRecord | None:
        with self._lock:
            for k in self._keys.values():
                if k.hashed_key == hashed_key:
                    return k
        return None

    def save_api_key(self, record: ApiKeyRecord) -> ApiKeyRecord:
        with self._lock:
            self._keys[record.id] = record
        return record

    def list_api_keys(self) -> list[ApiKeyRecord]:
        with self._lock:
            return sorted(self._keys.values(), key=lambda k: k.created_at, reverse=True)

    def revoke_api_key(self, key_id: str) -> bool:
        with self._lock:
            if key_id in self._keys:
                old = self._keys[key_id]
                self._keys[key_id] = ApiKeyRecord(
                    id=old.id,
                    client_id=old.client_id,
                    prefix=old.prefix,
                    hashed_key=old.hashed_key,
                    created_at=old.created_at,
                    expires_at=old.expires_at,
                    revoked=True,
                )
                return True
            return False

    def log_audit(self, record: ApiAuditLogRecord) -> None:
        with self._lock:
            self._logs.append(record)


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRunRecord] = {}
        self._lock = threading.Lock()

    def save(self, record: JobRunRecord) -> JobRunRecord:
        with self._lock:
            self._jobs[record.id] = record
        return record

    def get(self, job_id: str) -> JobRunRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update_status(
        self, job_id: str, status: str, result_id: str | None = None, error: str | None = None
    ) -> JobRunRecord | None:
        with self._lock:
            if job_id in self._jobs:
                old = self._jobs[job_id]
                self._jobs[job_id] = JobRunRecord(
                    id=old.id,
                    created_at=old.created_at,
                    updated_at=dt.datetime.now(dt.UTC),
                    status=status,
                    result_id=result_id,
                    error=error,
                )
                return self._jobs[job_id]
            return None
