"""remove sync runs table

Revision ID: 0005_remove_sync_runs
Revises: 0004_remove_auth_tables
Create Date: 2026-07-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_remove_sync_runs"
down_revision = "0004_remove_auth_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sync_runs")


def downgrade() -> None:
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stations_upserted", sa.Integer(), nullable=False),
        sa.Column("units_upserted", sa.Integer(), nullable=False),
        sa.Column("works_upserted", sa.Integer(), nullable=False),
        sa.Column("earnings_upserted", sa.Integer(), nullable=False),
        sa.Column("links_upserted", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
