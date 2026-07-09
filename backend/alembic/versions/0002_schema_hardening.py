"""schema hardening for audit columns, FKs, and indexes

Revision ID: 0002_schema_hardening
Revises: 0001_initial_pg_schema
Create Date: 2026-07-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_schema_hardening"
down_revision = "0001_initial_pg_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    audit_cols = [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]
    for table in ["stations", "units", "works", "earnings", "sync_runs"]:
        for col in audit_cols:
            op.add_column(table, sa.Column(col.name, col.type, nullable=True))
        op.execute(sa.text(f"UPDATE {table} SET created_at = COALESCE(created_at, NOW()), updated_at = COALESCE(updated_at, NOW())"))
        op.alter_column(table, "created_at", nullable=False)
        op.alter_column(table, "updated_at", nullable=False)

    op.create_unique_constraint("uq_units_station_unit", "units", ["station_code", "unit_no"])
    op.create_unique_constraint("uq_works_project_section", "works", ["project_id", "section"])
    op.create_unique_constraint("uq_work_links_scope", "work_links", ["project_id", "scope_type", "scope_value", "station_code"])
    op.create_unique_constraint("uq_earnings_unit_receipt", "earnings", ["unit_no", "receipt_key"])
    op.create_unique_constraint("uq_earning_links_receipt_unit_station", "earning_links", ["receipt_key", "unit_no", "station_code"])

    op.create_foreign_key("fk_units_station_code", "units", "stations", ["station_code"], ["station_code"], ondelete="SET NULL")
    op.create_foreign_key("fk_works_project_id", "work_links", "works", ["project_id"], ["project_id"], ondelete="CASCADE")
    op.create_foreign_key("fk_work_links_station_code", "work_links", "stations", ["station_code"], ["station_code"], ondelete="SET NULL")
    op.create_foreign_key("fk_earnings_unit_no", "earnings", "units", ["unit_no"], ["unit_no"], ondelete="SET NULL")
    op.create_foreign_key("fk_earnings_station_code", "earnings", "stations", ["station_code"], ["station_code"], ondelete="SET NULL")
    op.create_foreign_key("fk_earning_links_receipt_key", "earning_links", "earnings", ["receipt_key"], ["receipt_key"], ondelete="CASCADE")
    op.create_foreign_key("fk_earning_links_unit_no", "earning_links", "units", ["unit_no"], ["unit_no"], ondelete="SET NULL")
    op.create_foreign_key("fk_earning_links_station_code", "earning_links", "stations", ["station_code"], ["station_code"], ondelete="SET NULL")

    op.create_index("ix_stations_station_name", "stations", ["station_name"])
    op.create_index("ix_stations_division", "stations", ["division"])
    op.create_index("ix_stations_section", "stations", ["section"])
    op.create_index("ix_stations_categorisation", "stations", ["categorisation"])
    op.create_index("ix_stations_passenger_footfall", "stations", ["passenger_footfall"])
    op.create_index("ix_units_licensee_name", "units", ["licensee_name"])
    op.create_index("ix_units_unit_status", "units", ["unit_status"])
    op.create_index("ix_units_type_of_unit", "units", ["type_of_unit"])
    op.create_index("ix_works_status", "works", ["status"])
    op.create_index("ix_works_short_name_of_work", "works", ["short_name_of_work"])
    op.create_index("ix_works_section", "works", ["section"])
    op.create_index("ix_work_links_scope_type", "work_links", ["scope_type"])
    op.create_index("ix_work_links_match_status", "work_links", ["match_status"])
    op.create_index("ix_earnings_date_of_receipt", "earnings", ["date_of_receipt"])
    op.create_index("ix_earnings_licensee_name", "earnings", ["licensee_name"])
    op.create_index("ix_earnings_payment_head", "earnings", ["payment_head"])
    op.create_index("ix_earnings_payment_sub_head", "earnings", ["payment_sub_head"])
    op.create_index("ix_earnings_amount", "earnings", ["amount"])
    op.create_index("ix_earnings_receipt_type", "earnings", ["receipt_type"])
    op.create_index("ix_earnings_mr_no", "earnings", ["mr_no"])
    op.create_index("ix_earning_links_match_status", "earning_links", ["match_status"])


def downgrade() -> None:
    op.drop_index("ix_earning_links_match_status", table_name="earning_links")
    op.drop_index("ix_earnings_mr_no", table_name="earnings")
    op.drop_index("ix_earnings_receipt_type", table_name="earnings")
    op.drop_index("ix_earnings_amount", table_name="earnings")
    op.drop_index("ix_earnings_payment_sub_head", table_name="earnings")
    op.drop_index("ix_earnings_payment_head", table_name="earnings")
    op.drop_index("ix_earnings_licensee_name", table_name="earnings")
    op.drop_index("ix_earnings_date_of_receipt", table_name="earnings")
    op.drop_index("ix_work_links_match_status", table_name="work_links")
    op.drop_index("ix_work_links_scope_type", table_name="work_links")
    op.drop_index("ix_works_section", table_name="works")
    op.drop_index("ix_works_short_name_of_work", table_name="works")
    op.drop_index("ix_works_status", table_name="works")
    op.drop_index("ix_units_type_of_unit", table_name="units")
    op.drop_index("ix_units_unit_status", table_name="units")
    op.drop_index("ix_units_licensee_name", table_name="units")
    op.drop_index("ix_stations_passenger_footfall", table_name="stations")
    op.drop_index("ix_stations_categorisation", table_name="stations")
    op.drop_index("ix_stations_section", table_name="stations")
    op.drop_index("ix_stations_division", table_name="stations")
    op.drop_index("ix_stations_station_name", table_name="stations")

    op.drop_constraint("fk_earning_links_station_code", "earning_links", type_="foreignkey")
    op.drop_constraint("fk_earning_links_unit_no", "earning_links", type_="foreignkey")
    op.drop_constraint("fk_earning_links_receipt_key", "earning_links", type_="foreignkey")
    op.drop_constraint("fk_earnings_station_code", "earnings", type_="foreignkey")
    op.drop_constraint("fk_earnings_unit_no", "earnings", type_="foreignkey")
    op.drop_constraint("fk_work_links_station_code", "work_links", type_="foreignkey")
    op.drop_constraint("fk_works_project_id", "work_links", type_="foreignkey")
    op.drop_constraint("fk_units_station_code", "units", type_="foreignkey")

    op.drop_constraint("uq_earning_links_receipt_unit_station", "earning_links", type_="unique")
    op.drop_constraint("uq_earnings_unit_receipt", "earnings", type_="unique")
    op.drop_constraint("uq_work_links_scope", "work_links", type_="unique")
    op.drop_constraint("uq_works_project_section", "works", type_="unique")
    op.drop_constraint("uq_units_station_unit", "units", type_="unique")

    for table in ["stations", "units", "works", "earnings", "sync_runs"]:
        op.drop_column(table, "updated_at")
        op.drop_column(table, "created_at")
