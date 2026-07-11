"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("foreign_currency", sa.String(length=3), nullable=False),
        sa.Column("domestic_currency", sa.String(length=3), nullable=False),
        sa.Column("pair", sa.String(length=6), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("amount_foreign", sa.Float(), nullable=False),
        sa.Column("spot_rate", sa.Float(), nullable=False),
        sa.Column("forward_rate", sa.Float(), nullable=False),
        sa.Column("annualized_volatility", sa.Float(), nullable=False),
        sa.Column("budgeted_margin_pct", sa.Float(), nullable=False),
        sa.Column("probability_below_threshold", sa.Float(), nullable=False),
        sa.Column("expected_shortfall_margin_pct", sa.Float(), nullable=False),
        sa.Column("optimal_hedge_ratio", sa.Float(), nullable=False),
        sa.Column("hedged_margin_pct", sa.Float(), nullable=False),
        sa.Column("vulnerability_score", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    op.create_index("ix_simulation_runs_created_at", "simulation_runs", ["created_at"])
    op.create_index("ix_simulation_runs_pair", "simulation_runs", ["pair"])


def downgrade() -> None:
    op.drop_index("ix_simulation_runs_pair", table_name="simulation_runs")
    op.drop_index("ix_simulation_runs_created_at", table_name="simulation_runs")
    op.drop_table("simulation_runs")
