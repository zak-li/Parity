from __future__ import annotations

from core.models.enums import RiskLevel
from db import (
    CompositeSimulationRepository,
    InMemorySimulationRepository,
    PersistenceConfig,
    build_repository,
    record_from_result,
)
from db.config import load_persistence_config
from db.records import SimulationRecord


def test_record_from_result_extracts_summary(simulation_result):
    record = record_from_result(simulation_result)
    assert record.foreign_currency == "USD"
    assert record.domestic_currency == "MAD"
    assert record.pair == "USDMAD"
    assert 0 <= record.vulnerability_score <= 100
    assert isinstance(record.risk_level, RiskLevel)
    assert "instruments" in record.details


def test_record_summary_is_json_serializable(simulation_result):
    summary = record_from_result(simulation_result).summary()
    assert "details" not in summary
    assert isinstance(summary["created_at"], str)
    assert summary["risk_level"] in ("Faible", "Modéré", "Élevé", "Critique")


def test_in_memory_save_and_get(simulation_result):
    repo = InMemorySimulationRepository()
    record = repo.save(record_from_result(simulation_result))
    assert repo.get(record.id) == record
    assert repo.get("missing") is None


def test_in_memory_latest_for_pair_returns_most_recent(simulation_result):
    repo = InMemorySimulationRepository()
    first = record_from_result(simulation_result)
    second = record_from_result(simulation_result)
    repo.save(first)
    repo.save(second)
    latest = repo.latest_for_pair("USD", "MAD")
    assert latest.id == second.id
    assert repo.latest_for_pair("EUR", "MAD") is None


def test_in_memory_history_filters_and_limits(simulation_result):
    repo = InMemorySimulationRepository()
    for _ in range(3):
        repo.save(record_from_result(simulation_result))
    assert len(repo.history(limit=2)) == 2
    assert repo.history(foreign_currency="EUR") == []
    assert len(repo.history(foreign_currency="usd", domestic_currency="mad")) == 3


class _RecordingSink:
    def __init__(self, fail: bool = False):
        self.saved: list[SimulationRecord] = []
        self.closed = False
        self._fail = fail

    def save(self, record):
        if self._fail:
            raise RuntimeError("sink down")
        self.saved.append(record)
        return record

    def close(self):
        self.closed = True


def test_composite_writes_to_primary_and_secondaries(simulation_result):
    primary = InMemorySimulationRepository()
    sink = _RecordingSink()
    repo = CompositeSimulationRepository(primary, [sink])

    record = repo.save(record_from_result(simulation_result))
    assert primary.get(record.id) is not None
    assert sink.saved and sink.saved[0].id == record.id


def test_composite_survives_failing_secondary(simulation_result):
    primary = InMemorySimulationRepository()
    failing = _RecordingSink(fail=True)
    repo = CompositeSimulationRepository(primary, [failing])

    record = repo.save(record_from_result(simulation_result))
    assert primary.get(record.id) is not None


def test_composite_reads_from_primary(simulation_result):
    primary = InMemorySimulationRepository()
    repo = CompositeSimulationRepository(primary, [_RecordingSink()])
    record = repo.save(record_from_result(simulation_result))
    assert repo.get(record.id) == record
    assert repo.latest_for_pair("USD", "MAD").id == record.id
    assert len(repo.history()) == 1


def test_composite_exposure_summary_delegates(simulation_result):
    class _GraphSink(_RecordingSink):
        def exposure_summary(self):
            return [{"foreign": "USD", "domestic": "MAD", "runs": 1, "last_score": 42.0}]

    repo = CompositeSimulationRepository(InMemorySimulationRepository(), [_GraphSink()])
    assert repo.exposure_summary()[0]["foreign"] == "USD"


def test_composite_close_propagates(simulation_result):
    primary = InMemorySimulationRepository()
    sink = _RecordingSink()
    CompositeSimulationRepository(primary, [sink]).close()
    assert sink.closed


def test_build_repository_defaults_to_memory_when_unconfigured(monkeypatch):
    for key in list(__import__("os").environ):
        if key.startswith("XI_"):
            monkeypatch.delenv(key, raising=False)
    repo = build_repository(PersistenceConfig())
    assert isinstance(repo, InMemorySimulationRepository)


def test_config_enabled_flags():
    empty = PersistenceConfig()
    assert not empty.postgres_enabled
    assert not empty.mongodb_enabled
    assert not empty.neo4j_enabled

    full = PersistenceConfig(
        postgres_dsn="postgresql://x",
        mongodb_uri="mongodb://x",
        neo4j_uri="neo4j://x",
        neo4j_username="u",
        neo4j_password="p",
    )
    assert full.postgres_enabled and full.mongodb_enabled and full.neo4j_enabled


def test_load_persistence_config_reads_env(monkeypatch):
    monkeypatch.setenv("XI_POSTGRES_DSN", "postgresql://demo")
    monkeypatch.setenv("XI_MONGODB_DATABASE", "custom_db")
    config = load_persistence_config()
    assert config.postgres_dsn == "postgresql://demo"
    assert config.mongodb_database == "custom_db"
