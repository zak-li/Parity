from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase

from .records import SimulationRecord

_MERGE_QUERY = """
MERGE (f:Currency {code: $foreign})
MERGE (d:Currency {code: $domestic})
CREATE (s:SimulationRun {
    id: $id, created_at: $created_at, pair: $pair, amount_foreign: $amount,
    spot_rate: $spot, forward_rate: $forward, vulnerability_score: $score,
    risk_level: $risk_level, optimal_hedge_ratio: $hedge_ratio
})
MERGE (s)-[:EXPOSED_TO]->(f)
MERGE (s)-[:SETTLED_IN]->(d)
MERGE (f)-[e:EXPOSES]->(d)
SET e.last_score = $score, e.last_seen = $created_at, e.runs = coalesce(e.runs, 0) + 1
"""

_EXPOSURE_QUERY = """
MATCH (f:Currency)-[e:EXPOSES]->(d:Currency)
RETURN f.code AS foreign, d.code AS domestic, e.runs AS runs,
       e.last_score AS last_score
ORDER BY e.last_score DESC
"""


class Neo4jGraphRepository:
    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j") -> None:
        self._driver = GraphDatabase.driver(uri, auth=(username, password))
        self._database = database

    def save(self, record: SimulationRecord) -> SimulationRecord:
        with self._driver.session(database=self._database) as session:
            session.execute_write(
                lambda tx: tx.run(
                    _MERGE_QUERY,
                    foreign=record.foreign_currency,
                    domestic=record.domestic_currency,
                    id=record.id,
                    created_at=record.created_at.isoformat(),
                    pair=record.pair,
                    amount=record.amount_foreign,
                    spot=record.spot_rate,
                    forward=record.forward_rate,
                    score=record.vulnerability_score,
                    risk_level=record.risk_level.value,
                    hedge_ratio=record.optimal_hedge_ratio,
                )
            )
        return record

    def exposure_summary(self) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            result = session.execute_read(lambda tx: list(tx.run(_EXPOSURE_QUERY)))
        return [record.data() for record in result]

    def close(self) -> None:
        self._driver.close()
