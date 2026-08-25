"""Add normalized contract registry for station, train and other contracts."""

from alembic import op
import sqlalchemy as sa

revision = "0027_contract_registry"
down_revision = "0026_work_expenditure_updates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_registry_contractors",
        sa.Column("contractor_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("legal_name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False, unique=True),
        sa.Column("gst_number", sa.String(32)),
        sa.Column("pan_number", sa.String(32)),
        sa.Column("contact_details", sa.Text()),
        sa.Column("source_hash", sa.String(64)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_contract_registry_contractors_legal_name", "contract_registry_contractors", ["legal_name"])
    op.create_table(
        "contract_registry_contracts",
        sa.Column("contract_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_sl_no", sa.Integer()), sa.Column("source_system", sa.String(64), nullable=False),
        sa.Column("source_file", sa.Text()), sa.Column("source_sheet", sa.Text()), sa.Column("source_row_number", sa.Integer()),
        sa.Column("contract_number", sa.String(255)), sa.Column("contract_name", sa.Text(), nullable=False),
        sa.Column("contractor_id", sa.Integer(), sa.ForeignKey("contract_registry_contractors.contractor_id", ondelete="SET NULL")),
        sa.Column("contract_family", sa.String(64), nullable=False, server_default="other"), sa.Column("award_method", sa.String(64)),
        sa.Column("policy_code", sa.String(128)), sa.Column("category", sa.Text()), sa.Column("status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("status_reason", sa.Text()), sa.Column("contract_date", sa.Date()), sa.Column("loa_date", sa.Date()), sa.Column("commencement_date", sa.Date()),
        sa.Column("period_start", sa.Date()), sa.Column("period_end", sa.Date()), sa.Column("duration_value", sa.Numeric(10, 2)), sa.Column("duration_unit", sa.String(32)),
        sa.Column("annual_license_fee", sa.Numeric(14, 2)), sa.Column("quarterly_license_fee", sa.Numeric(14, 2)), sa.Column("total_contract_value", sa.Numeric(14, 2)),
        sa.Column("additional_license_fee", sa.Numeric(14, 2)), sa.Column("payment_frequency", sa.String(32)), sa.Column("remarks", sa.Text()),
        sa.Column("source_hash", sa.String(64)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("source_system", "contract_number", name="uq_contract_registry_source_number"),
    )
    for column in ("source_system", "contract_number", "contract_name", "contractor_id", "contract_family", "award_method", "policy_code", "category", "status", "period_start", "period_end"):
        op.create_index(f"ix_contract_registry_contracts_{column}", "contract_registry_contracts", [column])
    op.create_table(
        "contract_registry_assets",
        sa.Column("contract_asset_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contract_registry_contracts.contract_id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_type", sa.String(64), nullable=False), sa.Column("station_code", sa.String(64), sa.ForeignKey("stations.station_code", ondelete="SET NULL")),
        sa.Column("train_number", sa.String(128)), sa.Column("asset_name", sa.Text()), sa.Column("raw_asset_value", sa.Text()),
        sa.Column("match_status", sa.String(32), nullable=False, server_default="unmatched"),
        sa.UniqueConstraint("contract_id", "asset_type", "raw_asset_value", name="uq_contract_registry_asset"),
    )
    for column in ("contract_id", "asset_type", "station_code", "train_number", "match_status"):
        op.create_index(f"ix_contract_registry_assets_{column}", "contract_registry_assets", [column])
    op.create_table(
        "contract_registry_status_history",
        sa.Column("status_history_id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contract_registry_contracts.contract_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("effective_from", sa.Date()), sa.Column("effective_to", sa.Date()), sa.Column("reason", sa.Text()), sa.Column("source_reference", sa.Text()),
    )
    op.create_index("ix_contract_registry_status_history_contract_id", "contract_registry_status_history", ["contract_id"])
    op.create_index("ix_contract_registry_status_history_status", "contract_registry_status_history", ["status"])
    op.create_table(
        "contract_registry_payment_schedules",
        sa.Column("schedule_id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contract_registry_contracts.contract_id", ondelete="CASCADE"), nullable=False),
        sa.Column("installment_number", sa.Integer(), nullable=False), sa.Column("period_label", sa.Text()), sa.Column("due_date", sa.Date()), sa.Column("expected_amount", sa.Numeric(14, 2)), sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.UniqueConstraint("contract_id", "installment_number", name="uq_contract_registry_installment"),
    )
    op.create_index("ix_contract_registry_payment_schedules_contract_id", "contract_registry_payment_schedules", ["contract_id"])
    op.create_index("ix_contract_registry_payment_schedules_due_date", "contract_registry_payment_schedules", ["due_date"])
    op.create_table(
        "contract_registry_payments",
        sa.Column("payment_id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contract_registry_contracts.contract_id", ondelete="CASCADE"), nullable=False),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("contract_registry_payment_schedules.schedule_id", ondelete="SET NULL")), sa.Column("payment_date", sa.Date()), sa.Column("amount_due", sa.Numeric(14, 2)), sa.Column("amount_paid", sa.Numeric(14, 2)), sa.Column("interest_amount", sa.Numeric(14, 2), server_default="0"), sa.Column("delay_days", sa.Integer()), sa.Column("payment_reference", sa.Text()), sa.Column("payment_status", sa.String(32), nullable=False, server_default="pending"), sa.Column("source_reference", sa.Text()), sa.Column("remarks", sa.Text()),
        sa.Column("source_hash", sa.String(64)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    for column in ("contract_id", "schedule_id", "payment_status"):
        op.create_index(f"ix_contract_registry_payments_{column}", "contract_registry_payments", [column])


def downgrade() -> None:
    op.drop_table("contract_registry_payments")
    op.drop_table("contract_registry_payment_schedules")
    op.drop_table("contract_registry_status_history")
    op.drop_table("contract_registry_assets")
    op.drop_table("contract_registry_contracts")
    op.drop_table("contract_registry_contractors")
