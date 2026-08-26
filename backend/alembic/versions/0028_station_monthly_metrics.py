"""Add monthly station operating metrics."""
from alembic import op
import sqlalchemy as sa

revision = "0028_station_monthly_metrics"
down_revision = "0027_contract_registry"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "station_monthly_metrics",
        sa.Column("metric_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_code", sa.String(64), sa.ForeignKey("stations.station_code", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_month", sa.Date(), nullable=False),
        sa.Column("passenger_footfall", sa.Integer()),
        sa.Column("tickets_issued", sa.Integer()),
        sa.Column("earnings", sa.Numeric(14, 2)),
        sa.Column("source", sa.Text()), sa.Column("remarks", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("station_code", "metric_month", name="uq_station_monthly_metrics_station_month"),
    )
    op.create_index("ix_station_monthly_metrics_station_code", "station_monthly_metrics", ["station_code"])
    op.create_index("ix_station_monthly_metrics_metric_month", "station_monthly_metrics", ["metric_month"])

def downgrade() -> None:
    op.drop_index("ix_station_monthly_metrics_metric_month", table_name="station_monthly_metrics")
    op.drop_index("ix_station_monthly_metrics_station_code", table_name="station_monthly_metrics")
    op.drop_table("station_monthly_metrics")
