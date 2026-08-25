"""Add dated work progress history records.

Revision ID: 0019_work_progress_history
Revises: 0018_combined_accessibility
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_work_progress_history"
down_revision = "0018_combined_accessibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_progress_updates",
        sa.Column("progress_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("update_date", sa.String(length=32), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("physical_progress", sa.Text(), nullable=True),
        sa.Column("financial_progress", sa.Text(), nullable=True),
        sa.Column("expenditure_upto_date", sa.Integer(), nullable=True),
        sa.Column("tdc", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["works.project_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("progress_id"),
        sa.UniqueConstraint("project_id", "update_date", name="uq_work_progress_project_date"),
    )
    op.create_index("ix_work_progress_updates_project_id", "work_progress_updates", ["project_id"])
    op.create_index("ix_work_progress_updates_update_date", "work_progress_updates", ["update_date"])
    op.create_index("ix_work_progress_updates_status", "work_progress_updates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_work_progress_updates_status", table_name="work_progress_updates")
    op.drop_index("ix_work_progress_updates_update_date", table_name="work_progress_updates")
    op.drop_index("ix_work_progress_updates_project_id", table_name="work_progress_updates")
    op.drop_table("work_progress_updates")
