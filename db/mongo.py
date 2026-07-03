from __future__ import annotations

import datetime as dt

from pymongo import DESCENDING, MongoClient

from core.models.enums import RiskLevel

from .records import SimulationRecord


class MongoSimulationRepository:
    def __init__(
        self,
        uri: str,
        database: str = "xi",
        collection: str = "simulation_runs",
        server_selection_timeout_ms: int = 15000,
    ) -> None:
        self._client: MongoClient = MongoClient(
            uri, serverSelectionTimeoutMS=server_selection_timeout_ms, tz_aware=True
        )
        self._collection = self._client[database][collection]
        self._collection.create_index([("pair", DESCENDING), ("created_at", DESCENDING)])

    def save(self, record: SimulationRecord) -> SimulationRecord:
        self._collection.replace_one({"_id": record.id}, self._to_document(record), upsert=True)
        return record

    def get(self, record_id: str) -> SimulationRecord | None:
        document = self._collection.find_one({"_id": record_id})
        return self._from_document(document) if document else None

    def latest_for_pair(
        self, foreign_currency: str, domestic_currency: str
    ) -> SimulationRecord | None:
        pair = f"{foreign_currency}{domestic_currency}".upper()
        document = self._collection.find_one({"pair": pair}, sort=[("created_at", DESCENDING)])
        return self._from_document(document) if document else None

    def history(
        self,
        foreign_currency: str | None = None,
        domestic_currency: str | None = None,
        limit: int = 50,
    ) -> list[SimulationRecord]:
        query: dict = {}
        if foreign_currency:
            query["foreign_currency"] = foreign_currency.upper()
        if domestic_currency:
            query["domestic_currency"] = domestic_currency.upper()
        cursor = self._collection.find(query).sort("created_at", DESCENDING).limit(max(limit, 0))
        return [self._from_document(document) for document in cursor]

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _to_document(record: SimulationRecord) -> dict:
        return {
            "_id": record.id,
            "created_at": record.created_at,
            "foreign_currency": record.foreign_currency,
            "domestic_currency": record.domestic_currency,
            "pair": record.pair,
            "order_date": record.order_date.isoformat(),
            "delivery_date": record.delivery_date.isoformat(),
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
    def _from_document(document: dict) -> SimulationRecord:
        created = document["created_at"]
        if created.tzinfo is None:
            created = created.replace(tzinfo=dt.timezone.utc)
        return SimulationRecord(
            id=document["_id"],
            created_at=created,
            foreign_currency=document["foreign_currency"],
            domestic_currency=document["domestic_currency"],
            order_date=dt.date.fromisoformat(document["order_date"]),
            delivery_date=dt.date.fromisoformat(document["delivery_date"]),
            horizon_days=document["horizon_days"],
            amount_foreign=document["amount_foreign"],
            spot_rate=document["spot_rate"],
            forward_rate=document["forward_rate"],
            annualized_volatility=document["annualized_volatility"],
            budgeted_margin_pct=document["budgeted_margin_pct"],
            probability_below_threshold=document["probability_below_threshold"],
            expected_shortfall_margin_pct=document["expected_shortfall_margin_pct"],
            optimal_hedge_ratio=document["optimal_hedge_ratio"],
            hedged_margin_pct=document["hedged_margin_pct"],
            vulnerability_score=document["vulnerability_score"],
            risk_level=RiskLevel(document["risk_level"]),
            recommendation=document["recommendation"],
            details=document.get("details", {}),
        )
