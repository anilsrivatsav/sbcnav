"""Store scheduled report executions and snapshots.

Revision ID: 0025_report_runs
Revises: 0024_report_presets
"""

from alembic import op
import sqlalchemy as sa


revision = "0025_report_runs"
down_revision = "0024_report_presets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column("preset_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("report_json", sa.Text()),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.ForeignKeyConstraint(["preset_id"], ["report_presets.preset_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_report_runs_preset_id", "report_runs", ["preset_id"])
    op.create_index("ix_report_runs_status", "report_runs", ["status"])
    op.create_index("ix_report_runs_generated_at", "report_runs", ["generated_at"])


def downgrade() -> None:
    op.drop_index("ix_report_runs_generated_at", table_name="report_runs")
    op.drop_index("ix_report_runs_status", table_name="report_runs")
    op.drop_index("ix_report_runs_preset_id", table_name="report_runs")
    op.drop_table("report_runs")
