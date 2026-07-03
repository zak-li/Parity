from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
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
)
from sqlalchemy.engine import URL

from core.models.enums import RiskLevel

from .records import SimulationRecord

_metadata = MetaData()

_simulation_runs = Table(
    "simulation_runs",
    _metadata,
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
        _metadata.create_all(self._engine)

    def save(self, record: SimulationRecord) -> SimulationRecord:
        with self._engine.begin() as connection:
            connection.execute(insert(_simulation_runs).values(**self._to_row(record)))
        return record

    def get(self, record_id: str) -> SimulationRecord | None:
        stmt = select(_simulation_runs).where(_simulation_runs.c.id == record_id)
        with self._engine.connect() as connection:
            row = connection.execute(stmt).mappings().first()
        return self._from_row(row) if row else None

    def latest_for_pair(
        self, foreign_currency: str, domestic_currency: str
    ) -> SimulationRecord | None:
        pair = f"{foreign_currency}{domestic_currency}".upper()
        stmt = (
            select(_simulation_runs)
            .where(_simulation_runs.c.pair == pair)
            .order_by(_simulation_runs.c.created_at.desc())
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
        stmt = select(_simulation_runs).order_by(_simulation_runs.c.created_at.desc())
        if foreign_currency:
            stmt = stmt.where(_simulation_runs.c.foreign_currency == foreign_currency.upper())
        if domestic_currency:
            stmt = stmt.where(_simulation_runs.c.domestic_currency == domestic_currency.upper())
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
            created = created.replace(tzinfo=dt.timezone.utc)
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
