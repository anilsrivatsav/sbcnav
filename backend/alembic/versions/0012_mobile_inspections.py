"""add offline mobile inspection domain

Revision ID: 0012_mobile_inspections
Revises: 0011_work_source_fields
Create Date: 2026-07-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_mobile_inspections"
down_revision = "0011_work_source_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inspection_templates",
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("template_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition_json", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("template_id"),
        sa.UniqueConstraint("template_code", "version", name="uq_inspection_templates_code_version"),
    )
    op.create_index("ix_inspection_templates_template_code", "inspection_templates", ["template_code"])
    op.create_index("ix_inspection_templates_name", "inspection_templates", ["name"])
    op.create_index("ix_inspection_templates_domain", "inspection_templates", ["domain"])

    op.create_table(
        "inspections",
        sa.Column("inspection_id", sa.String(length=36), nullable=False),
        sa.Column("station_code", sa.String(length=64), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("inspector_name", sa.String(length=255), nullable=False),
        sa.Column("inspection_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("server_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["station_code"], ["stations.station_code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_id"], ["inspection_templates.template_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("inspection_id"),
    )
    for column in ("station_code", "template_id", "inspector_name", "inspection_type", "status", "device_id", "started_at"):
        op.create_index(f"ix_inspections_{column}", "inspections", [column])

    op.create_table(
        "inspection_responses",
        sa.Column("response_id", sa.String(length=36), nullable=False),
        sa.Column("inspection_id", sa.String(length=36), nullable=False),
        sa.Column("section_code", sa.String(length=64), nullable=False),
        sa.Column("question_code", sa.String(length=128), nullable=False),
        sa.Column("response_value", sa.String(length=64), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("asset_ref", sa.String(length=128), nullable=True),
        sa.Column("platform", sa.String(length=64), nullable=True),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column("client_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("server_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.inspection_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("response_id"),
    )
    for column in ("inspection_id", "section_code", "question_code", "response_value", "severity", "asset_ref", "platform"):
        op.create_index(f"ix_inspection_responses_{column}", "inspection_responses", [column])

    op.create_table(
        "inspection_findings",
        sa.Column("finding_id", sa.String(length=36), nullable=False),
        sa.Column("inspection_id", sa.String(length=36), nullable=False),
        sa.Column("response_id", sa.String(length=36), nullable=True),
        sa.Column("station_code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("responsible_party", sa.String(length=255), nullable=True),
        sa.Column("target_date", sa.String(length=32), nullable=True),
        sa.Column("financial_implication", sa.Integer(), nullable=True),
        sa.Column("repeat_observation", sa.Boolean(), nullable=False),
        sa.Column("client_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("server_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.inspection_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["response_id"], ["inspection_responses.response_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["station_code"], ["stations.station_code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("finding_id"),
    )
    for column in ("inspection_id", "response_id", "station_code", "title", "severity", "status", "responsible_party", "target_date", "repeat_observation"):
        op.create_index(f"ix_inspection_findings_{column}", "inspection_findings", [column])

    op.create_table(
        "mobile_sync_operations",
        sa.Column("operation_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("operation_id"),
    )
    for column in ("device_id", "entity_type", "entity_id", "status"):
        op.create_index(f"ix_mobile_sync_operations_{column}", "mobile_sync_operations", [column])

    op.create_table(
        "mobile_changes",
        sa.Column("sequence", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("sequence"),
    )
    for column in ("entity_type", "entity_id", "changed_at"):
        op.create_index(f"ix_mobile_changes_{column}", "mobile_changes", [column])


def downgrade() -> None:
    op.drop_table("mobile_changes")
    op.drop_table("mobile_sync_operations")
    op.drop_table("inspection_findings")
    op.drop_table("inspection_responses")
    op.drop_table("inspections")
    op.drop_table("inspection_templates")
