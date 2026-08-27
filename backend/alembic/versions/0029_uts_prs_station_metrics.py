"""Add UTS and PRS monthly station measures."""
from alembic import op
import sqlalchemy as sa

revision = "0029_uts_prs_station_metrics"
down_revision = "0028_station_monthly_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("station_monthly_metrics")}
    if "uts_tickets" not in columns:
        op.add_column("station_monthly_metrics", sa.Column("uts_tickets", sa.Integer()))
    if "uts_earnings" not in columns:
        op.add_column("station_monthly_metrics", sa.Column("uts_earnings", sa.Numeric(14, 2)))
    if "prs_tickets" not in columns:
        op.add_column("station_monthly_metrics", sa.Column("prs_tickets", sa.Integer()))
    if "prs_earnings" not in columns:
        op.add_column("station_monthly_metrics", sa.Column("prs_earnings", sa.Numeric(14, 2)))


def downgrade() -> None:
    op.drop_column("station_monthly_metrics", "prs_earnings")
    op.drop_column("station_monthly_metrics", "prs_tickets")
    op.drop_column("station_monthly_metrics", "uts_earnings")
    op.drop_column("station_monthly_metrics", "uts_tickets")
