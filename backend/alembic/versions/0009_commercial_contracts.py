"""add commercial contracts

Revision ID: 0009_commercial_contracts
Revises: 0008_pf_extension_status
Create Date: 2026-07-18 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_commercial_contracts"
down_revision = "0008_pf_extension_status"
branch_labels = None
depends_on = None


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("source_hash", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "commercial_contracts",
        sa.Column("contract_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_sl_no", sa.Integer()),
        sa.Column("raw_station_value", sa.Text()),
        sa.Column("contract_name", sa.String(length=255), nullable=False),
        sa.Column("licensee_name", sa.Text()),
        sa.Column("allocation_code", sa.String(length=64)),
        sa.Column("contract_allotted_on", sa.Text()),
        sa.Column("policy", sa.Text()),
        sa.Column("sub_category", sa.Text()),
        sa.Column("asset_scope", sa.Text()),
        sa.Column("space_sq_ft", sa.Integer()),
        sa.Column("annual_license_fee", sa.Integer()),
        sa.Column("quarterly_license_fee", sa.Integer()),
        sa.Column("no_of_years", sa.Integer()),
        sa.Column("contract_period_from", sa.Text()),
        sa.Column("contract_upto", sa.Text()),
        sa.Column("cycle", sa.Text()),
        sa.Column("year_ending_amount", sa.Integer()),
        sa.Column("total_license_fee_2026_2027", sa.Integer()),
        sa.Column("station_match_status", sa.Text()),
        sa.Column("remarks", sa.Text()),
        *audit_columns(),
        sa.UniqueConstraint("contract_name", name="uq_commercial_contracts_contract_name"),
    )
    for column in [
        "source_sl_no",
        "raw_station_value",
        "contract_name",
        "licensee_name",
        "allocation_code",
        "contract_allotted_on",
        "policy",
        "sub_category",
        "asset_scope",
        "annual_license_fee",
        "quarterly_license_fee",
        "contract_period_from",
        "contract_upto",
        "cycle",
        "station_match_status",
    ]:
        op.create_index(f"ix_commercial_contracts_{column}", "commercial_contracts", [column])

    op.create_table(
        "commercial_contract_station_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contract_key", sa.Integer(), nullable=False),
        sa.Column("station_code", sa.String(length=64)),
        sa.Column("raw_station_value", sa.Text()),
        sa.Column("match_type", sa.Text()),
        sa.Column("match_status", sa.Text()),
        sa.ForeignKeyConstraint(["contract_key"], ["commercial_contracts.contract_key"], name="fk_commercial_contract_links_contract_key", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["station_code"], ["stations.station_code"], name="fk_commercial_contract_links_station_code", ondelete="SET NULL"),
        sa.UniqueConstraint("contract_key", "station_code", "raw_station_value", "match_type", name="uq_commercial_contract_station_link"),
    )
    for column in ["contract_key", "station_code", "raw_station_value", "match_type", "match_status"]:
        op.create_index(f"ix_commercial_contract_station_links_{column}", "commercial_contract_station_links", [column])

    op.create_table(
        "commercial_contract_payments",
        sa.Column("payment_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contract_key", sa.Integer(), nullable=False),
        sa.Column("payment_month", sa.String(length=16), nullable=False),
        sa.Column("source_column", sa.Text()),
        sa.Column("amount_due", sa.Integer()),
        sa.Column("amount_paid", sa.Integer()),
        sa.Column("payment_status", sa.Text()),
        *audit_columns(),
        sa.ForeignKeyConstraint(["contract_key"], ["commercial_contracts.contract_key"], name="fk_commercial_contract_payments_contract_key", ondelete="CASCADE"),
        sa.UniqueConstraint("contract_key", "payment_month", name="uq_commercial_contract_payment_month"),
    )
    for column in ["contract_key", "payment_month", "amount_due", "amount_paid", "payment_status"]:
        op.create_index(f"ix_commercial_contract_payments_{column}", "commercial_contract_payments", [column])


def downgrade() -> None:
    op.drop_table("commercial_contract_payments")
    op.drop_table("commercial_contract_station_links")
    op.drop_table("commercial_contracts")
