"""Store periodic work expenditure history.

Revision ID: 0026_work_expenditure_updates
Revises: 0025_report_runs
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_work_expenditure_updates"
down_revision = "0025_report_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_expenditure_updates",
        sa.Column("expenditure_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("update_date", sa.String(length=32), nullable=False),
        sa.Column("period_expenditure", sa.Integer()),
        sa.Column("cumulative_expenditure", sa.Integer()),
        sa.Column("source", sa.Text()),
        sa.Column("reference", sa.Text()),
        sa.Column("remarks", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["works.project_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "update_date", name="uq_work_expenditure_project_date"),
    )
    op.create_index("ix_work_expenditure_updates_project_id", "work_expenditure_updates", ["project_id"])
    op.create_index("ix_work_expenditure_updates_update_date", "work_expenditure_updates", ["update_date"])
    op.create_index("ix_work_expenditure_updates_cumulative_expenditure", "work_expenditure_updates", ["cumulative_expenditure"])


def downgrade() -> None:
    op.drop_index("ix_work_expenditure_updates_cumulative_expenditure", table_name="work_expenditure_updates")
    op.drop_index("ix_work_expenditure_updates_update_date", table_name="work_expenditure_updates")
    op.drop_index("ix_work_expenditure_updates_project_id", table_name="work_expenditure_updates")
    op.drop_table("work_expenditure_updates")
