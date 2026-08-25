"""Persist report presets and schedule metadata.

Revision ID: 0024_report_presets
Revises: 0023_contract_lifecycle_fields
"""

from alembic import op
import sqlalchemy as sa


revision = "0024_report_presets"
down_revision = "0023_contract_lifecycle_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_presets",
        sa.Column("preset_id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("report_tab", sa.String(length=64), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=False),
        sa.Column("schedule", sa.String(length=32)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(length=128)),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_report_presets_name"),
    )
    op.create_index("ix_report_presets_name", "report_presets", ["name"])
    op.create_index("ix_report_presets_report_tab", "report_presets", ["report_tab"])
    op.create_index("ix_report_presets_schedule", "report_presets", ["schedule"])
    op.create_index("ix_report_presets_is_active", "report_presets", ["is_active"])
    op.create_index("ix_report_presets_next_run_at", "report_presets", ["next_run_at"])


def downgrade() -> None:
    op.drop_index("ix_report_presets_next_run_at", table_name="report_presets")
    op.drop_index("ix_report_presets_is_active", table_name="report_presets")
    op.drop_index("ix_report_presets_schedule", table_name="report_presets")
    op.drop_index("ix_report_presets_report_tab", table_name="report_presets")
    op.drop_index("ix_report_presets_name", table_name="report_presets")
    op.drop_table("report_presets")
