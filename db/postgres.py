from __future__ import annotations

import datetime as dt
import os

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    insert,
    select,
    update,
)
from sqlalchemy.engine import URL

from core.models.enums import RiskLevel

from .records import ApiAuditLogRecord, ApiKeyRecord, JobRunRecord, SimulationRecord

metadata = MetaData()

simulation_runs = Table(
    "simulation_runs",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("foreign_currency", String(3), nullable=False),
    Column("domestic_currency", String(3), nullable=False),
    Column("pair", String(6), nullable=False, index=True),
    Column("order_date", Date, nullable=False),
    Column("delivery_date", Date, nullable=False),
    Column("horizon_days", Integer, nullable=False),
    Column("amount_foreign", Float, nullable=False),
    Column("spot_rate", Float, nullable=False),
    Column("forward_rate", Float, nullable=False),
    Column("annualized_volatility", Float, nullable=False),
    Column("budgeted_margin_pct", Float, nullable=False),
    Column("probability_below_threshold", Float, nullable=False),
    Column("expected_shortfall_margin_pct", Float, nullable=False),
    Column("optimal_hedge_ratio", Float, nullable=False),
    Column("hedged_margin_pct", Float, nullable=False),
    Column("vulnerability_score", Integer, nullable=False),
    Column("risk_level", String(16), nullable=False),
    Column("recommendation", Text, nullable=False),
    Column("details", JSON, nullable=False),
)

api_keys = Table(
    "api_keys",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("client_id", String(64), nullable=False, index=True),
    Column("prefix", String(8), nullable=False),
    Column("hashed_key", String(128), nullable=False, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=True),
    Column("revoked", Boolean, nullable=False, default=False),
)

api_audit_logs = Table(
    "api_audit_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("timestamp", DateTime(timezone=True), nullable=False, index=True),
    Column("client_id", String(64), nullable=False, index=True),
    Column("endpoint", String(128), nullable=False),
    Column("method", String(16), nullable=False),
    Column("status_code", Integer, nullable=False),
    Column("processing_time_ms", Float, nullable=False),
)

job_runs = Table(
    "job_runs",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("status", String(16), nullable=False, index=True),
    Column("result_id", String(32), nullable=True),
    Column("error", Text, nullable=True),
)


def _make_url(dsn: str) -> URL:
    body = dsn.split("://", 1)[1]
    userinfo, hostpart = body.rsplit("@", 1)
    username, password = userinfo.split(":", 1)
    hostport, rest = hostpart.split("/", 1)
    host, port = hostport.rsplit(":", 1)
    database = rest.split("?", 1)[0]
    return URL.create(
        "postgresql+psycopg2",
        username=username,
        password=password,
        host=host,
        port=int(port),
        database=database,
        query={"sslmode": "require"},
    )


class PostgresSimulationRepository:
    def __init__(self, dsn: str, connect_timeout: int = 15) -> None:
        self._engine = create_engine(
            _make_url(dsn),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            connect_args={"connect_timeout": connect_timeout},
        )
        # In production the schema is owned by Alembic migrations
        # (`alembic upgrade head`); set XI_DB_AUTO_CREATE=0 to disable auto-create.
        if os.environ.get("XI_DB_AUTO_CREATE", "1") == "1":
            metadata.create_all(self._engine)

    def save(self, record: SimulationRecord) -> SimulationRecord:
        with self._engine.begin() as connection:
            connection.execute(insert(simulation_runs).values(**self._to_row(record)))
        return record

    def get(self, record_id: str) -> SimulationRecord | None:
        stmt = select(simulation_runs).where(simulation_runs.c.id == record_id)
        with self._engine.connect() as connection:
            row = connection.execute(stmt).mappings().first()
        return self._from_row(row) if row else None

    def latest_for_pair(
        self, foreign_currency: str, domestic_currency: str
    ) -> SimulationRecord | None:
        pair = f"{foreign_currency}{domestic_currency}".upper()
        stmt = (
            select(simulation_runs)
            .where(simulation_runs.c.pair == pair)
            .order_by(simulation_runs.c.created_at.desc())
            .limit(1)
        )
        with self._engine.connect() as connection:
            row = connection.execute(stmt).mappings().first()
        return self._from_row(row) if row else None

    def history(
        self,
        foreign_currency: str | None = None,
        domestic_currency: str | None = None,
        limit: int = 50,
    ) -> list[SimulationRecord]:
        stmt = select(simulation_runs).order_by(simulation_runs.c.created_at.desc())
        if foreign_currency:
            stmt = stmt.where(simulation_runs.c.foreign_currency == foreign_currency.upper())
        if domestic_currency:
            stmt = stmt.where(simulation_runs.c.domestic_currency == domestic_currency.upper())
        stmt = stmt.limit(max(limit, 0))
        with self._engine.connect() as connection:
            rows = connection.execute(stmt).mappings().all()
        return [self._from_row(row) for row in rows]

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _to_row(record: SimulationRecord) -> dict:
        return {
            "id": record.id,
            "created_at": record.created_at,
            "foreign_currency": record.foreign_currency,
            "domestic_currency": record.domestic_currency,
            "pair": record.pair,
            "order_date": record.order_date,
            "delivery_date": record.delivery_date,
            "horizon_days": record.horizon_days,
            "amount_foreign": record.amount_foreign,
            "spot_rate": record.spot_rate,
            "forward_rate": record.forward_rate,
            "annualized_volatility": record.annualized_volatility,
            "budgeted_margin_pct": record.budgeted_margin_pct,
            "probability_below_threshold": record.probability_below_threshold,
            "expected_shortfall_margin_pct": record.expected_shortfall_margin_pct,
            "optimal_hedge_ratio": record.optimal_hedge_ratio,
            "hedged_margin_pct": record.hedged_margin_pct,
            "vulnerability_score": record.vulnerability_score,
            "risk_level": record.risk_level.value,
            "recommendation": record.recommendation,
            "details": record.details,
        }

    @staticmethod
    def _from_row(row) -> SimulationRecord:
        created = row["created_at"]
        if created.tzinfo is None:
            created = created.replace(tzinfo=dt.UTC)
        return SimulationRecord(
            id=row["id"],
            created_at=created,
            foreign_currency=row["foreign_currency"],
            domestic_currency=row["domestic_currency"],
            order_date=row["order_date"],
            delivery_date=row["delivery_date"],
            horizon_days=row["horizon_days"],
            amount_foreign=row["amount_foreign"],
            spot_rate=row["spot_rate"],
            forward_rate=row["forward_rate"],
            annualized_volatility=row["annualized_volatility"],
            budgeted_margin_pct=row["budgeted_margin_pct"],
            probability_below_threshold=row["probability_below_threshold"],
            expected_shortfall_margin_pct=row["expected_shortfall_margin_pct"],
            optimal_hedge_ratio=row["optimal_hedge_ratio"],
            hedged_margin_pct=row["hedged_margin_pct"],
            vulnerability_score=row["vulnerability_score"],
            risk_level=RiskLevel(row["risk_level"]),
            recommendation=row["recommendation"],
            details=row["details"],
        )


class PostgresAuthRepository:
    def __init__(self, engine) -> None:
        self._engine = engine

    def get_api_key(self, hashed_key: str) -> ApiKeyRecord | None:
        stmt = select(api_keys).where(api_keys.c.hashed_key == hashed_key)
        with self._engine.connect() as connection:
            row = connection.execute(stmt).mappings().first()
        return self._from_row(row) if row else None

    def save_api_key(self, record: ApiKeyRecord) -> ApiKeyRecord:
        with self._engine.begin() as connection:
            connection.execute(insert(api_keys).values(**self._to_row(record)))
        return record

    def revoke_api_key(self, key_id: str) -> bool:
        stmt = update(api_keys).where(api_keys.c.id == key_id).values(revoked=True)
        with self._engine.begin() as connection:
            res = connection.execute(stmt)
        return res.rowcount > 0

    def log_audit(self, record: ApiAuditLogRecord) -> None:
        data = {
            "timestamp": record.timestamp,
            "client_id": record.client_id,
            "endpoint": record.endpoint,
            "method": record.method,
            "status_code": record.status_code,
            "processing_time_ms": record.processing_time_ms,
        }
        with self._engine.begin() as connection:
            connection.execute(insert(api_audit_logs).values(**data))

    @staticmethod
    def _to_row(record: ApiKeyRecord) -> dict:
        return {
            "id": record.id,
            "client_id": record.client_id,
            "prefix": record.prefix,
            "hashed_key": record.hashed_key,
            "created_at": record.created_at,
            "expires_at": record.expires_at,
            "revoked": record.revoked,
        }

    @staticmethod
    def _from_row(row) -> ApiKeyRecord:
        created = row["created_at"]
        if created.tzinfo is None:
            created = created.replace(tzinfo=dt.UTC)
        expires = row["expires_at"]
        if expires and expires.tzinfo is None:
            expires = expires.replace(tzinfo=dt.UTC)
        return ApiKeyRecord(
            id=row["id"],
            client_id=row["client_id"],
            prefix=row["prefix"],
            hashed_key=row["hashed_key"],
            created_at=created,
            expires_at=expires,
            revoked=row["revoked"],
        )


class PostgresJobRepository:
    def __init__(self, engine) -> None:
        self._engine = engine

    def save(self, record: JobRunRecord) -> JobRunRecord:
        with self._engine.begin() as connection:
            connection.execute(insert(job_runs).values(**self._to_row(record)))
        return record

    def get(self, job_id: str) -> JobRunRecord | None:
        stmt = select(job_runs).where(job_runs.c.id == job_id)
        with self._engine.connect() as connection:
            row = connection.execute(stmt).mappings().first()
        return self._from_row(row) if row else None

    def update_status(
        self, job_id: str, status: str, result_id: str | None = None, error: str | None = None
    ) -> JobRunRecord | None:
        stmt = (
            update(job_runs)
            .where(job_runs.c.id == job_id)
            .values(
                status=status, result_id=result_id, error=error, updated_at=dt.datetime.now(dt.UTC)
            )
        )
        with self._engine.begin() as connection:
            connection.execute(stmt)
        return self.get(job_id)

    @staticmethod
    def _to_row(record: JobRunRecord) -> dict:
        return {
            "id": record.id,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "status": record.status,
            "result_id": record.result_id,
            "error": record.error,
        }

    @staticmethod
    def _from_row(row) -> JobRunRecord:
        created = row["created_at"]
        if created.tzinfo is None:
            created = created.replace(tzinfo=dt.UTC)
        updated = row["updated_at"]
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=dt.UTC)
        return JobRunRecord(
            id=row["id"],
            created_at=created,
            updated_at=updated,
            status=row["status"],
            result_id=row["result_id"],
            error=row["error"],
        )
