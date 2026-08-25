"""Add target date of completion to sanctioned works."""

from alembic import op
import sqlalchemy as sa


revision = "0020_work_tdc"
down_revision = "0019_work_progress_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("works", sa.Column("tdc", sa.Text(), nullable=True))
    op.create_index("ix_works_tdc", "works", ["tdc"])


def downgrade() -> None:
    op.drop_index("ix_works_tdc", table_name="works")
    op.drop_column("works", "tdc")
