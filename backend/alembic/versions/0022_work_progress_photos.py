"""Store progress photographs linked to work updates.

Revision ID: 0022_work_progress_photos
Revises: 0021_mobile_device_states
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_work_progress_photos"
down_revision = "0021_mobile_device_states"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_progress_photos",
        sa.Column("photo_id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("progress_id", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("caption", sa.Text()),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["works.project_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["progress_id"], ["work_progress_updates.progress_id"], ondelete="SET NULL"),
    )
    op.create_index("ix_work_progress_photos_project_id", "work_progress_photos", ["project_id"])
    op.create_index("ix_work_progress_photos_progress_id", "work_progress_photos", ["progress_id"])


def downgrade() -> None:
    op.drop_index("ix_work_progress_photos_progress_id", table_name="work_progress_photos")
    op.drop_index("ix_work_progress_photos_project_id", table_name="work_progress_photos")
    op.drop_table("work_progress_photos")
