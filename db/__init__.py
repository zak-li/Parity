from __future__ import annotations

import logging

from .base import SimulationRepository
from .composite import CompositeSimulationRepository, SimulationSink
from .config import PersistenceConfig, load_persistence_config
from .memory import InMemorySimulationRepository
from .records import SimulationRecord, record_from_result

logger = logging.getLogger(__name__)

__all__ = [
    "CompositeSimulationRepository",
    "InMemorySimulationRepository",
    "PersistenceConfig",
    "SimulationRecord",
    "SimulationRepository",
    "SimulationSink",
    "build_repository",
    "load_persistence_config",
    "record_from_result",
]


def build_repository(config: PersistenceConfig | None = None) -> SimulationRepository:
    config = config or load_persistence_config()

    primary: SimulationRepository = InMemorySimulationRepository()
    secondaries: list[SimulationSink] = []

    if config.postgres_enabled:
        try:
            from .postgres import PostgresSimulationRepository

            primary = PostgresSimulationRepository(config.postgres_dsn)  # type: ignore[arg-type]
        except Exception as exc:
            logger.warning("postgres_unavailable", extra={"error": str(exc)})

    if config.mongodb_enabled:
        try:
            from .mongo import MongoSimulationRepository

            mongo = MongoSimulationRepository(config.mongodb_uri, config.mongodb_database)  # type: ignore[arg-type]
            if isinstance(primary, InMemorySimulationRepository):
                primary = mongo
            else:
                secondaries.append(mongo)
        except Exception as exc:
            logger.warning("mongodb_unavailable", extra={"error": str(exc)})

    if config.neo4j_enabled:
        try:
            from .neo4j_graph import Neo4jGraphRepository

            secondaries.append(
                Neo4jGraphRepository(
                    config.neo4j_uri,  # type: ignore[arg-type]
                    config.neo4j_username,  # type: ignore[arg-type]
                    config.neo4j_password,  # type: ignore[arg-type]
                    config.neo4j_database,
                )
            )
        except Exception as exc:
            logger.warning("neo4j_unavailable", extra={"error": str(exc)})

    if secondaries:
        return CompositeSimulationRepository(primary, secondaries)
    return primary
