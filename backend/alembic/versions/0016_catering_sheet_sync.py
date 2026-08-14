"""Add lossless catering sheet fields and sync history.

Revision ID: 0016_catering_sheet_sync
Revises: 0015_correct_mys_den_assignment
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_catering_sheet_sync"
down_revision = "0015_correct_mys_den_assignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("units", sa.Column("paid_upto", sa.Text(), nullable=True))
    op.add_column("units", sa.Column("source_row", sa.Integer(), nullable=True))
    op.create_index("ix_units_paid_upto", "units", ["paid_upto"])

    op.add_column("earnings", sa.Column("source_rows", sa.Text(), nullable=True))
    op.add_column("earnings", sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("earnings", sa.Column("raw_unit_no", sa.Text(), nullable=True))
    op.add_column("earnings", sa.Column("raw_station_code", sa.Text(), nullable=True))
    op.add_column("earnings", sa.Column("earning_scope", sa.String(length=32), nullable=True))
    op.create_index("ix_earnings_raw_unit_no", "earnings", ["raw_unit_no"])
    op.create_index("ix_earnings_raw_station_code", "earnings", ["raw_station_code"])
    op.create_index("ix_earnings_earning_scope", "earnings", ["earning_scope"])

    op.create_table(
        "catering_sync_runs",
        sa.Column("sync_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_spreadsheet_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unit_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("earning_source_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("earning_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("linked_earnings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unlinked_earnings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_catering_sync_runs_source_spreadsheet_id", "catering_sync_runs", ["source_spreadsheet_id"])
    op.create_index("ix_catering_sync_runs_status", "catering_sync_runs", ["status"])
    op.create_index("ix_catering_sync_runs_started_at", "catering_sync_runs", ["started_at"])


def downgrade() -> None:
    op.drop_table("catering_sync_runs")
    op.drop_index("ix_earnings_earning_scope", table_name="earnings")
    op.drop_index("ix_earnings_raw_station_code", table_name="earnings")
    op.drop_index("ix_earnings_raw_unit_no", table_name="earnings")
    op.drop_column("earnings", "earning_scope")
    op.drop_column("earnings", "raw_station_code")
    op.drop_column("earnings", "raw_unit_no")
    op.drop_column("earnings", "duplicate_count")
    op.drop_column("earnings", "source_rows")
    op.drop_index("ix_units_paid_upto", table_name="units")
    op.drop_column("units", "source_row")
    op.drop_column("units", "paid_upto")
