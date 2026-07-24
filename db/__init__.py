from __future__ import annotations

import logging
import os

from .base import AuthRepository, JobRepository, SimulationRepository
from .composite import CompositeSimulationRepository, SimulationSink
from .config import PersistenceConfig, load_persistence_config
from .memory import InMemoryAuthRepository, InMemoryJobRepository, InMemorySimulationRepository
from .records import (
    ApiAuditLogRecord,
    ApiKeyRecord,
    JobRunRecord,
    SimulationRecord,
    record_from_result,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ApiAuditLogRecord",
    "ApiKeyRecord",
    "AuthRepository",
    "CompositeSimulationRepository",
    "InMemoryAuthRepository",
    "InMemoryJobRepository",
    "InMemorySimulationRepository",
    "JobRepository",
    "JobRunRecord",
    "PersistenceConfig",
    "SimulationRecord",
    "SimulationRepository",
    "SimulationSink",
    "build_auth_repository",
    "build_job_repository",
    "build_repository",
    "load_persistence_config",
    "record_from_result",
]


def _strict_persistence() -> bool:
    # When set, a configured-but-unreachable database is a hard error instead of
    # a silent fall-back to volatile in-memory storage (which would lose data).
    return os.environ.get("XI_DB_STRICT", "0") == "1"


def build_repository(config: PersistenceConfig | None = None) -> SimulationRepository:
    config = config or load_persistence_config()
    strict = _strict_persistence()

    primary: SimulationRepository = InMemorySimulationRepository()
    secondaries: list[SimulationSink] = []

    if config.postgres_enabled:
        try:
            from .postgres import PostgresSimulationRepository

            primary = PostgresSimulationRepository(config.postgres_dsn)  # type: ignore[arg-type]
        except Exception as exc:
            logger.warning("postgres_unavailable", extra={"error": str(exc)})
            if strict:
                raise

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
            if strict:
                raise

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
            if strict:
                raise

    if secondaries:
        return CompositeSimulationRepository(primary, secondaries)
    return primary


def build_auth_repository(config: PersistenceConfig | None = None) -> AuthRepository:
    config = config or load_persistence_config()
    if config.postgres_enabled:
        try:
            from sqlalchemy import create_engine

            from .postgres import PostgresAuthRepository, _make_url

            engine = create_engine(_make_url(config.postgres_dsn), pool_size=5, max_overflow=5)  # type: ignore[arg-type]
            return PostgresAuthRepository(engine)
        except Exception as exc:
            logger.warning("postgres_auth_unavailable", extra={"error": str(exc)})

    return InMemoryAuthRepository()


def build_job_repository(config: PersistenceConfig | None = None) -> JobRepository:
    config = config or load_persistence_config()
    if config.postgres_enabled:
        try:
            from sqlalchemy import create_engine

            from .postgres import PostgresJobRepository, _make_url

            engine = create_engine(_make_url(config.postgres_dsn), pool_size=5, max_overflow=5)  # type: ignore[arg-type]
            return PostgresJobRepository(engine)
        except Exception as exc:
            logger.warning("postgres_job_unavailable", extra={"error": str(exc)})

    return InMemoryJobRepository()
