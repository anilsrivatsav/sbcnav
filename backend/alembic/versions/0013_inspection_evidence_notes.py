"""add inspection photo evidence and contextual notes

Revision ID: 0013_inspection_evidence_notes
Revises: 0012_mobile_inspections
Create Date: 2026-07-27 20:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_inspection_evidence_notes"
down_revision = "0012_mobile_inspections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inspection_evidence",
        sa.Column("evidence_id", sa.String(length=36), nullable=False),
        sa.Column("inspection_id", sa.String(length=36), nullable=False),
        sa.Column("response_id", sa.String(length=36), nullable=True),
        sa.Column("question_code", sa.String(length=128), nullable=True),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("client_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("server_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["inspections.inspection_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["response_id"],
            ["inspection_responses.response_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("evidence_id"),
    )
    for column in ("inspection_id", "response_id", "question_code"):
        op.create_index(
            f"ix_inspection_evidence_{column}",
            "inspection_evidence",
            [column],
        )

    op.create_table(
        "inspection_notes",
        sa.Column("note_id", sa.String(length=36), nullable=False),
        sa.Column("inspection_id", sa.String(length=36), nullable=False),
        sa.Column("section_code", sa.String(length=64), nullable=True),
        sa.Column("question_code", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("client_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("server_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["inspections.inspection_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("note_id"),
    )
    for column in ("inspection_id", "section_code", "question_code"):
        op.create_index(
            f"ix_inspection_notes_{column}",
            "inspection_notes",
            [column],
        )


def downgrade() -> None:
    op.drop_table("inspection_notes")
    op.drop_table("inspection_evidence")
