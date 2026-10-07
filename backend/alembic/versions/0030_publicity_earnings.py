"""Historical publicity receipt ledger and versioned Main Sheet imports."""
from alembic import op
import sqlalchemy as sa

revision = "0030_publicity_earnings"
down_revision = "0029_uts_prs_station_metrics"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("publicity_earnings_imports",
        sa.Column("import_id", sa.String(64), primary_key=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False))
    op.create_table("publicity_earnings",
        sa.Column("import_id", sa.String(64), sa.ForeignKey("publicity_earnings_imports.import_id"), primary_key=True),
        sa.Column("source_row", sa.Integer(), primary_key=True),
        sa.Column("financial_year", sa.String(7), nullable=False),
        sa.Column("month", sa.Integer()),
        sa.Column("receipt_date", sa.Date()),
        *[sa.Column(name, sa.Text()) for name in ("details", "policy", "firm", "location", "detailed_head", "allocation_code", "receipt_reference")],
        *[sa.Column(name, sa.Numeric(24, 10)) for name in ("pub_earnings", "nfr_earnings", "licence_fee", "penalty", "app_based_cab", "gst", "total_with_gst")],
        sa.Column("source_values", sa.JSON(), nullable=False),
        sa.CheckConstraint("month IS NULL OR (month >= 1 AND month <= 12)", name="ck_publicity_month"))
    op.create_index("ix_publicity_earnings_financial_year", "publicity_earnings", ["financial_year"])
    op.create_index("ix_publicity_earnings_policy", "publicity_earnings", ["policy"])
    op.create_table("publicity_earnings_current",
        sa.Column("dataset", sa.String(32), primary_key=True),
        sa.Column("import_id", sa.String(64), sa.ForeignKey("publicity_earnings_imports.import_id")))
    op.execute("INSERT INTO publicity_earnings_current (dataset) VALUES ('main_sheet')")


def downgrade():
    op.drop_table("publicity_earnings_current")
    op.drop_table("publicity_earnings")
    op.drop_table("publicity_earnings_imports")
