"""initial PostgreSQL schema

Revision ID: 0001_initial_pg_schema
Revises:
Create Date: 2026-07-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_pg_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stations",
        sa.Column("station_code", sa.String(length=64), primary_key=True),
        sa.Column("station_name", sa.Text()),
        sa.Column("division", sa.Text()),
        sa.Column("zone", sa.Text()),
        sa.Column("section", sa.Text()),
        sa.Column("cmi", sa.Text()),
        sa.Column("den", sa.Text()),
        sa.Column("sr_den", sa.Text()),
        sa.Column("categorisation", sa.Text()),
        sa.Column("earnings_range", sa.Text()),
        sa.Column("passenger_range", sa.Text()),
        sa.Column("passenger_footfall", sa.Integer()),
        sa.Column("platforms", sa.Text()),
        sa.Column("number_of_platforms", sa.Integer()),
        sa.Column("platform_type", sa.Text()),
        sa.Column("parking", sa.Text()),
        sa.Column("pay_and_use", sa.Text()),
        sa.Column("trains_dealt", sa.Integer()),
        sa.Column("tickets_per_day", sa.Integer()),
        sa.Column("passengers_per_day", sa.Integer()),
        sa.Column("earnings_per_day", sa.Integer()),
        sa.Column("footfalls_per_day", sa.Integer()),
        sa.Column("source_hash", sa.String(length=64)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "units",
        sa.Column("unit_no", sa.String(length=64), primary_key=True),
        sa.Column("sl_no", sa.Integer()),
        sa.Column("type_of_unit", sa.Text()),
        sa.Column("station_code", sa.String(length=64)),
        sa.Column("station_category", sa.Text()),
        sa.Column("old_category", sa.Text()),
        sa.Column("pf_no", sa.Text()),
        sa.Column("pegged_location", sa.Text()),
        sa.Column("reservation_category", sa.Text()),
        sa.Column("allotment_type", sa.Text()),
        sa.Column("licensee_name", sa.Text()),
        sa.Column("license_fee", sa.Text()),
        sa.Column("contract_from", sa.Text()),
        sa.Column("contract_to", sa.Text()),
        sa.Column("unit_status", sa.Text()),
        sa.Column("source_hash", sa.String(length=64)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_units_station_code", "units", ["station_code"])
    op.create_table(
        "works",
        sa.Column("work_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("year_of_sanction", sa.Text()),
        sa.Column("year_ub_works", sa.Text()),
        sa.Column("status", sa.Text()),
        sa.Column("date_of_sanction", sa.Text()),
        sa.Column("short_name_of_work", sa.Text()),
        sa.Column("block_section_station", sa.Text()),
        sa.Column("allocation", sa.Text()),
        sa.Column("engg_remarks", sa.Text()),
        sa.Column("if_ub", sa.Text()),
        sa.Column("parent_work", sa.Text()),
        sa.Column("section", sa.Text()),
        sa.Column("anticipated_expenditure", sa.Integer()),
        sa.Column("remarks", sa.Text()),
        sa.Column("source_hash", sa.String(length=64)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("project_id", name="uq_works_project_id"),
    )
    op.create_index("ix_works_project_id", "works", ["project_id"])
    op.create_table(
        "work_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("scope_type", sa.Text()),
        sa.Column("scope_value", sa.Text()),
        sa.Column("station_code", sa.String(length=64)),
        sa.Column("match_status", sa.Text()),
    )
    op.create_index("ix_work_links_project_id", "work_links", ["project_id"])
    op.create_index("ix_work_links_station_code", "work_links", ["station_code"])
    op.create_table(
        "earnings",
        sa.Column("earning_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("receipt_key", sa.String(length=128), nullable=False),
        sa.Column("sl_no", sa.Integer()),
        sa.Column("date_of_receipt", sa.Text()),
        sa.Column("unit_no", sa.String(length=64)),
        sa.Column("station_code", sa.String(length=64)),
        sa.Column("pf_no", sa.Text()),
        sa.Column("licensee_name", sa.Text()),
        sa.Column("payment_head", sa.Text()),
        sa.Column("payment_sub_head", sa.Text()),
        sa.Column("period_from", sa.Text()),
        sa.Column("period_to", sa.Text()),
        sa.Column("amount", sa.Integer()),
        sa.Column("gst", sa.Integer()),
        sa.Column("receipt_type", sa.Text()),
        sa.Column("mr_no", sa.Text()),
        sa.Column("mr_date", sa.Text()),
        sa.Column("ua_case", sa.Text()),
        sa.Column("source_hash", sa.String(length=64)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("receipt_key", name="uq_earnings_receipt_key"),
    )
    op.create_index("ix_earnings_receipt_key", "earnings", ["receipt_key"])
    op.create_index("ix_earnings_unit_no", "earnings", ["unit_no"])
    op.create_index("ix_earnings_station_code", "earnings", ["station_code"])
    op.create_table(
        "earning_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("receipt_key", sa.String(length=128), nullable=False),
        sa.Column("unit_no", sa.String(length=64)),
        sa.Column("station_code", sa.String(length=64)),
        sa.Column("match_status", sa.Text()),
    )
    op.create_index("ix_earning_links_receipt_key", "earning_links", ["receipt_key"])
    op.create_index("ix_earning_links_unit_no", "earning_links", ["unit_no"])
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
    )


def downgrade() -> None:
    op.drop_table("sync_runs")
    op.drop_index("ix_earning_links_unit_no", table_name="earning_links")
    op.drop_index("ix_earning_links_receipt_key", table_name="earning_links")
    op.drop_table("earning_links")
    op.drop_index("ix_earnings_station_code", table_name="earnings")
    op.drop_index("ix_earnings_unit_no", table_name="earnings")
    op.drop_index("ix_earnings_receipt_key", table_name="earnings")
    op.drop_table("earnings")
    op.drop_index("ix_work_links_station_code", table_name="work_links")
    op.drop_index("ix_work_links_project_id", table_name="work_links")
    op.drop_table("work_links")
    op.drop_index("ix_works_project_id", table_name="works")
    op.drop_table("works")
    op.drop_index("ix_units_station_code", table_name="units")
    op.drop_table("units")
    op.drop_table("stations")
