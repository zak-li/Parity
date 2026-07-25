"""simulation client_id (multi-tenant isolation)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing rows predate multi-tenancy; the server_default backfills them to
    # the shared "public" bucket so no run leaks into a real tenant's history.
    op.add_column(
        "simulation_runs",
        sa.Column(
            "client_id",
            sa.String(length=64),
            nullable=False,
            server_default="public",
        ),
    )
    op.create_index("ix_simulation_runs_client_id", "simulation_runs", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_simulation_runs_client_id", table_name="simulation_runs")
    op.drop_column("simulation_runs", "client_id")
