"""Store station-wise details from the combined lifts/escalators/ramps tab.

Revision ID: 0018_combined_accessibility
Revises: 0017_available_catering_units
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_combined_accessibility"
down_revision = "0017_available_catering_units"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("station_platform_extension_status", sa.Column("footfall_day", sa.Integer(), nullable=True))
    op.add_column("station_platform_extension_status", sa.Column("lift_details", sa.Text(), nullable=True))
    op.add_column("station_platform_extension_status", sa.Column("ramp_details", sa.Text(), nullable=True))
    op.add_column("station_platform_extension_status", sa.Column("escalator_details", sa.Text(), nullable=True))
    op.add_column("station_platform_extension_status", sa.Column("accessibility_source", sa.Text(), nullable=True))
    op.create_index("ix_station_platform_extension_status_footfall_day", "station_platform_extension_status", ["footfall_day"])


def downgrade() -> None:
    op.drop_index("ix_station_platform_extension_status_footfall_day", table_name="station_platform_extension_status")
    op.drop_column("station_platform_extension_status", "accessibility_source")
    op.drop_column("station_platform_extension_status", "escalator_details")
    op.drop_column("station_platform_extension_status", "ramp_details")
    op.drop_column("station_platform_extension_status", "lift_details")
    op.drop_column("station_platform_extension_status", "footfall_day")
