from __future__ import annotations

import db.mongo as mongo_module
import db.neo4j_graph as neo4j_module
import db.postgres as postgres_module
from db import (
    CompositeSimulationRepository,
    InMemorySimulationRepository,
    PersistenceConfig,
    build_repository,
)
from db.memory import InMemorySimulationRepository as MemRepo


class _FakePrimary(MemRepo):
    def __init__(self, *args, **kwargs):
        super().__init__()


class _FakeSink:
    def __init__(self, *args, **kwargs):
        self.args = args

    def save(self, record):
        return record

    def close(self):
        return None


def test_build_repository_wires_postgres_primary(monkeypatch):
    monkeypatch.setattr(postgres_module, "PostgresSimulationRepository", _FakePrimary)
    config = PersistenceConfig(postgres_dsn="postgresql://demo")
    repo = build_repository(config)
    assert isinstance(repo, _FakePrimary)


def test_build_repository_mongo_becomes_primary_without_postgres(monkeypatch):
    monkeypatch.setattr(mongo_module, "MongoSimulationRepository", _FakePrimary)
    config = PersistenceConfig(mongodb_uri="mongodb://demo")
    repo = build_repository(config)
    assert isinstance(repo, _FakePrimary)


def test_build_repository_composes_all_backends(monkeypatch):
    monkeypatch.setattr(postgres_module, "PostgresSimulationRepository", _FakePrimary)
    monkeypatch.setattr(mongo_module, "MongoSimulationRepository", _FakeSink)
    monkeypatch.setattr(neo4j_module, "Neo4jGraphRepository", _FakeSink)
    config = PersistenceConfig(
        postgres_dsn="postgresql://demo",
        mongodb_uri="mongodb://demo",
        neo4j_uri="neo4j://demo",
        neo4j_username="u",
        neo4j_password="p",
    )
    repo = build_repository(config)
    assert isinstance(repo, CompositeSimulationRepository)


def test_build_repository_degrades_when_backend_raises(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("connexion impossible")

    monkeypatch.setattr(postgres_module, "PostgresSimulationRepository", _boom)
    config = PersistenceConfig(postgres_dsn="postgresql://demo")
    repo = build_repository(config)
    assert isinstance(repo, InMemorySimulationRepository)
