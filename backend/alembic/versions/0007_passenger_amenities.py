"""add passenger amenity tables

Revision ID: 0007_passenger_amenities
Revises: 0006_data_change_logs
Create Date: 2026-07-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_passenger_amenities"
down_revision = "0006_data_change_logs"
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
        "amenity_norms",
        sa.Column("norm_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("amenity", sa.Text()),
        sa.Column("norm", sa.Text(), nullable=False),
        sa.Column("norm_quantity", sa.Text()),
        *audit_columns(),
        sa.UniqueConstraint("category", "amenity", "norm", name="uq_amenity_norms_category_amenity_norm"),
    )
    op.create_index("ix_amenity_norms_category", "amenity_norms", ["category"])
    op.create_index("ix_amenity_norms_amenity", "amenity_norms", ["amenity"])
    op.create_index("ix_amenity_norms_norm", "amenity_norms", ["norm"])

    op.create_table(
        "station_infra",
        sa.Column("infra_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_code", sa.String(length=64), nullable=False),
        sa.Column("station_name", sa.Text()),
        sa.Column("category", sa.Text()),
        sa.Column("platform_list", sa.Text()),
        sa.Column("platform_count", sa.Integer()),
        sa.Column("platform_level", sa.Text()),
        sa.Column("fob_details", sa.Text()),
        sa.Column("shelter_details", sa.Text()),
        sa.Column("remarks", sa.Text()),
        *audit_columns(),
        sa.UniqueConstraint("station_code", name="uq_station_infra_station_code"),
    )
    for column in ["station_code", "station_name", "category", "platform_count", "platform_level"]:
        op.create_index(f"ix_station_infra_{column}", "station_infra", [column])

    op.create_table(
        "platform_details",
        sa.Column("platform_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_code", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("length_m", sa.Integer()),
        sa.Column("lifts", sa.Text()),
        sa.Column("escalators", sa.Text()),
        sa.Column("ramp", sa.Text()),
        *audit_columns(),
        sa.UniqueConstraint("station_code", "platform", name="uq_platform_details_station_platform"),
    )
    for column in ["station_code", "platform", "length_m"]:
        op.create_index(f"ix_platform_details_{column}", "platform_details", [column])

    op.create_table(
        "wheel_chair_availability",
        sa.Column("wheel_chair_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_code", sa.String(length=64), nullable=False),
        sa.Column("station_name", sa.Text()),
        sa.Column("section", sa.Text()),
        sa.Column("category", sa.Text()),
        sa.Column("available_good_condition", sa.Integer()),
        *audit_columns(),
        sa.UniqueConstraint("station_code", name="uq_wheel_chair_station_code"),
    )
    for column in ["station_code", "station_name", "section", "category", "available_good_condition"]:
        op.create_index(f"ix_wheel_chair_availability_{column}", "wheel_chair_availability", [column])

    op.create_table(
        "trolley_paths",
        sa.Column("trolley_path_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_code", sa.String(length=64), nullable=False),
        sa.Column("station_name", sa.Text()),
        sa.Column("division", sa.Text()),
        sa.Column("zone", sa.Text()),
        sa.Column("section", sa.Text()),
        sa.Column("categorisation", sa.Text()),
        sa.Column("passenger_footfall", sa.Integer()),
        sa.Column("platforms", sa.Text()),
        sa.Column("number_of_platforms", sa.Text()),
        sa.Column("platform_type", sa.Text()),
        sa.Column("trolley_path", sa.Text()),
        sa.Column("trolley_path_sanction", sa.Text()),
        *audit_columns(),
        sa.UniqueConstraint("station_code", name="uq_trolley_paths_station_code"),
    )
    for column in ["station_code", "station_name", "division", "section", "categorisation", "passenger_footfall", "platform_type", "trolley_path"]:
        op.create_index(f"ix_trolley_paths_{column}", "trolley_paths", [column])

    op.create_table(
        "passenger_amenity_works",
        sa.Column("pa_work_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("work_type", sa.String(length=64), nullable=False),
        sa.Column("station_code", sa.String(length=64)),
        sa.Column("project_id", sa.String(length=128)),
        sa.Column("station_category", sa.Text()),
        sa.Column("platform_level", sa.Text()),
        sa.Column("work_name", sa.Text(), nullable=False),
        sa.Column("tender_status", sa.Text()),
        sa.Column("loa_date", sa.Text()),
        sa.Column("sanction_date", sa.Text()),
        sa.Column("executive_agency", sa.Text()),
        sa.Column("progress", sa.Text()),
        sa.Column("physical_progress", sa.Text()),
        sa.Column("tdc", sa.Text()),
        sa.Column("cost", sa.Text()),
        sa.Column("existing_platform_length", sa.Text()),
        *audit_columns(),
        sa.UniqueConstraint("work_type", "station_code", "work_name", name="uq_pa_works_type_station_name"),
    )
    for column in ["work_type", "station_code", "project_id", "station_category", "work_name", "tender_status", "sanction_date", "executive_agency", "tdc"]:
        op.create_index(f"ix_passenger_amenity_works_{column}", "passenger_amenity_works", [column])


def downgrade() -> None:
    op.drop_table("passenger_amenity_works")
    op.drop_table("trolley_paths")
    op.drop_table("wheel_chair_availability")
    op.drop_table("platform_details")
    op.drop_table("station_infra")
    op.drop_table("amenity_norms")
