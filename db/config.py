from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PersistenceConfig:
    postgres_dsn: str | None = None
    mongodb_uri: str | None = None
    mongodb_database: str = "xi"
    neo4j_uri: str | None = None
    neo4j_username: str | None = None
    neo4j_password: str | None = None
    neo4j_database: str = "neo4j"

    @property
    def postgres_enabled(self) -> bool:
        return bool(self.postgres_dsn)

    @property
    def mongodb_enabled(self) -> bool:
        return bool(self.mongodb_uri)

    @property
    def neo4j_enabled(self) -> bool:
        return bool(self.neo4j_uri and self.neo4j_username and self.neo4j_password)


def load_persistence_config() -> PersistenceConfig:
    def get(name: str) -> str | None:
        value = os.environ.get(f"XI_{name}")
        return value.strip() if value and value.strip() else None

    return PersistenceConfig(
        postgres_dsn=get("POSTGRES_DSN"),
        mongodb_uri=get("MONGODB_URI"),
        mongodb_database=get("MONGODB_DATABASE") or "xi",
        neo4j_uri=get("NEO4J_URI"),
        neo4j_username=get("NEO4J_USERNAME"),
        neo4j_password=get("NEO4J_PASSWORD"),
        neo4j_database=get("NEO4J_DATABASE") or "neo4j",
    )
