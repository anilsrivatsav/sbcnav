"""add sanctioned work source fields

Revision ID: 0011_work_source_fields
Revises: 0010_comm_station_links
Create Date: 2026-07-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_work_source_fields"
down_revision = "0010_comm_station_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("works", sa.Column("source_sn", sa.Integer(), nullable=True))
    op.add_column("works", sa.Column("source_project_id", sa.Text(), nullable=True))
    op.add_column("works", sa.Column("cost", sa.Integer(), nullable=True))
    op.add_column("works", sa.Column("expenditure_upto_date", sa.Integer(), nullable=True))
    op.add_column("works", sa.Column("physical_progress", sa.Text(), nullable=True))
    op.add_column("works", sa.Column("financial_progress", sa.Text(), nullable=True))
    op.execute("UPDATE works SET source_project_id = project_id WHERE source_project_id IS NULL")
    op.create_index("ix_works_source_sn", "works", ["source_sn"])
    op.create_index("ix_works_source_project_id", "works", ["source_project_id"])


def downgrade() -> None:
    op.drop_index("ix_works_source_project_id", table_name="works")
    op.drop_index("ix_works_source_sn", table_name="works")
    op.drop_column("works", "financial_progress")
    op.drop_column("works", "physical_progress")
    op.drop_column("works", "expenditure_upto_date")
    op.drop_column("works", "cost")
    op.drop_column("works", "source_project_id")
    op.drop_column("works", "source_sn")
