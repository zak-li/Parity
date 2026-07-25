from __future__ import annotations

import pytest

import db
from db.config import PersistenceConfig
from db.memory import InMemorySimulationRepository


class _Boom:
    def __init__(self, *args, **kwargs) -> None:
        raise RuntimeError("database is down")


def test_strict_persistence_reraises_when_db_down(monkeypatch):
    monkeypatch.setattr("db.postgres.PostgresSimulationRepository", _Boom)
    monkeypatch.setenv("XI_DB_STRICT", "1")
    cfg = PersistenceConfig(postgres_dsn="postgresql+psycopg2://user:pw@nowhere/db")
    with pytest.raises(RuntimeError):
        db.build_repository(cfg)


def test_strict_persistence_reraises_when_mongo_down(monkeypatch):
    monkeypatch.setattr("db.mongo.MongoSimulationRepository", _Boom)
    monkeypatch.setenv("XI_DB_STRICT", "1")
    cfg = PersistenceConfig(mongodb_uri="mongodb://nowhere:27017")
    with pytest.raises(RuntimeError):
        db.build_repository(cfg)


def test_strict_persistence_reraises_when_neo4j_down(monkeypatch):
    monkeypatch.setattr("db.neo4j_graph.Neo4jGraphRepository", _Boom)
    monkeypatch.setenv("XI_DB_STRICT", "1")
    cfg = PersistenceConfig(neo4j_uri="bolt://nowhere:7687", neo4j_username="u", neo4j_password="p")
    with pytest.raises(RuntimeError):
        db.build_repository(cfg)


def test_non_strict_falls_back_to_memory(monkeypatch):
    monkeypatch.setattr("db.postgres.PostgresSimulationRepository", _Boom)
    monkeypatch.setenv("XI_DB_STRICT", "0")
    cfg = PersistenceConfig(postgres_dsn="postgresql+psycopg2://user:pw@nowhere/db")
    repo = db.build_repository(cfg)
    assert isinstance(repo, InMemorySimulationRepository)
