"""add data change logs

Revision ID: 0006_data_change_logs
Revises: 0005_remove_sync_runs
Create Date: 2026-07-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_data_change_logs"
down_revision = "0005_remove_sync_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_change_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("resource", sa.String(length=32), nullable=False),
        sa.Column("record_key", sa.String(length=128)),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_data_change_logs_resource", "data_change_logs", ["resource"])
    op.create_index("ix_data_change_logs_record_key", "data_change_logs", ["record_key"])
    op.create_index("ix_data_change_logs_action", "data_change_logs", ["action"])
    op.create_index("ix_data_change_logs_source", "data_change_logs", ["source"])


def downgrade() -> None:
    op.drop_index("ix_data_change_logs_source", table_name="data_change_logs")
    op.drop_index("ix_data_change_logs_action", table_name="data_change_logs")
    op.drop_index("ix_data_change_logs_record_key", table_name="data_change_logs")
    op.drop_index("ix_data_change_logs_resource", table_name="data_change_logs")
    op.drop_table("data_change_logs")
