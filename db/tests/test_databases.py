from unittest.mock import patch

from db.memory import InMemorySimulationRepository
from db.mongo import MongoSimulationRepository
from db.neo4j_graph import Neo4jGraphRepository
from db.postgres import PostgresSimulationRepository


def test_postgres_manager():
    with patch("db.postgres.create_engine"):
        pm = PostgresSimulationRepository("postgresql://user:pass@test:5432/db")
        assert pm._engine is not None


def test_mongo_manager():
    with patch("db.mongo.MongoClient"):
        mm = MongoSimulationRepository("mongodb://test")
        assert mm._client is not None


def test_neo4j_manager():
    with patch("db.neo4j_graph.GraphDatabase.driver"):
        nm = Neo4jGraphRepository("bolt://test", "user", "pass")
        assert nm._driver is not None


def test_in_memory_db():
    mem = InMemorySimulationRepository()
    assert mem is not None
