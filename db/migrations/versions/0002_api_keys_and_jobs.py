"""api keys and jobs

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # api_keys
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=8), nullable=False),
        sa.Column("hashed_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_api_keys_client_id", "api_keys", ["client_id"])
    op.create_unique_constraint("uq_api_keys_hashed_key", "api_keys", ["hashed_key"])

    # api_audit_logs
    op.create_table(
        "api_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=128), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("processing_time_ms", sa.Float(), nullable=False),
    )
    op.create_index("ix_api_audit_logs_timestamp", "api_audit_logs", ["timestamp"])
    op.create_index("ix_api_audit_logs_client_id", "api_audit_logs", ["client_id"])

    # job_runs
    op.create_table(
        "job_runs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("result_id", sa.String(length=32), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_job_runs_created_at", "job_runs", ["created_at"])
    op.create_index("ix_job_runs_status", "job_runs", ["status"])


def downgrade() -> None:
    # job_runs
    op.drop_index("ix_job_runs_status", table_name="job_runs")
    op.drop_index("ix_job_runs_created_at", table_name="job_runs")
    op.drop_table("job_runs")

    # api_audit_logs
    op.drop_index("ix_api_audit_logs_client_id", table_name="api_audit_logs")
    op.drop_index("ix_api_audit_logs_timestamp", table_name="api_audit_logs")
    op.drop_table("api_audit_logs")

    # api_keys
    op.drop_constraint("uq_api_keys_hashed_key", table_name="api_keys", type_="unique")
    op.drop_index("ix_api_keys_client_id", table_name="api_keys")
    op.drop_table("api_keys")
