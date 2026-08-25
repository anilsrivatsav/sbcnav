"""Track offline cache state reported by mobile devices.

Revision ID: 0021_mobile_device_states
Revises: 0020_work_tdc
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_mobile_device_states"
down_revision = "0020_work_tdc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mobile_device_states",
        sa.Column("device_id", sa.String(length=128), primary_key=True),
        sa.Column("cached_stations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_station_details", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_works", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_earnings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_operations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_operations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("data_version", sa.String(length=128)),
        sa.Column("cache_updated_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_mobile_device_states_last_seen_at", "mobile_device_states", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_mobile_device_states_last_seen_at", table_name="mobile_device_states")
    op.drop_table("mobile_device_states")
