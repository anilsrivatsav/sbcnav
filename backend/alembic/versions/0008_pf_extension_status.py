"""add platform extension station status

Revision ID: 0008_pf_extension_status
Revises: 0007_passenger_amenities
Create Date: 2026-07-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_pf_extension_status"
down_revision = "0007_passenger_amenities"
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
        "platform_extension_summaries",
        sa.Column("summary_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("summary_type", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("station_count", sa.Integer()),
        sa.Column("full_length_platforms", sa.Integer()),
        sa.Column("work_under_progress", sa.Text()),
        sa.Column("pf_extension_proposed", sa.Text()),
        sa.Column("raising_extension_proposed", sa.Text()),
        sa.Column("platform_extension_work_proposed", sa.Text()),
        sa.Column("existing_length", sa.Text()),
        sa.Column("required_length", sa.Text()),
        sa.Column("fob_ramps_stairs_available", sa.Text()),
        sa.Column("stations_without_fob", sa.Text()),
        sa.Column("stations_with_fob_ramp", sa.Text()),
        sa.Column("stations_fob_wip", sa.Text()),
        sa.Column("stations_with_lift", sa.Text()),
        sa.Column("stations_lift_proposed", sa.Text()),
        sa.Column("stations_ramp_proposed", sa.Text()),
        sa.Column("stations_not_feasible_lift_ramp", sa.Text()),
        sa.Column("remarks", sa.Text()),
        sa.Column("source_row", sa.Integer()),
        *audit_columns(),
        sa.UniqueConstraint("summary_type", "category", name="uq_pf_extension_summary_type_category"),
    )
    op.create_index("ix_platform_extension_summaries_summary_type", "platform_extension_summaries", ["summary_type"])
    op.create_index("ix_platform_extension_summaries_category", "platform_extension_summaries", ["category"])
    op.create_index("ix_platform_extension_summaries_station_count", "platform_extension_summaries", ["station_count"])

    op.create_table(
        "station_platform_extension_status",
        sa.Column("status_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_code", sa.String(length=64), nullable=False),
        sa.Column("category", sa.Text()),
        sa.Column("source_category", sa.Text()),
        sa.Column("station_detail_category_code", sa.Text()),
        sa.Column("pf_extension_wip", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pf_extension_proposed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("raising_extension_proposed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("platform_extension_work_proposed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ramp_feasible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fob_without", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fob_ramp_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fob_wip", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("lift_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("lift_proposed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ramp_proposed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("not_feasible_lift_ramp", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_rows", sa.Text()),
        sa.Column("status_text", sa.Text()),
        sa.Column("remarks", sa.Text()),
        *audit_columns(),
        sa.UniqueConstraint("station_code", name="uq_station_pf_extension_status_station_code"),
    )
    for column in [
        "station_code",
        "category",
        "source_category",
        "station_detail_category_code",
        "pf_extension_wip",
        "pf_extension_proposed",
        "raising_extension_proposed",
        "platform_extension_work_proposed",
        "ramp_feasible",
        "fob_without",
        "fob_ramp_available",
        "fob_wip",
        "lift_available",
        "lift_proposed",
        "ramp_proposed",
        "not_feasible_lift_ramp",
    ]:
        op.create_index(f"ix_station_platform_extension_status_{column}", "station_platform_extension_status", [column])


def downgrade() -> None:
    op.drop_table("station_platform_extension_status")
    op.drop_table("platform_extension_summaries")
