"""Correct Sr DEN assignment for SBC MYS section stations."""

from alembic import op
import sqlalchemy as sa


revision = "0015_correct_mys_den_assignment"
down_revision = "0014_station_program_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE stations SET sr_den = 'Sanchit Srivatsava' "
            "WHERE upper(coalesce(division, '')) = 'SBC' "
            "AND upper(coalesce(section, '')) LIKE '%MYS%'"
        )
    )


def downgrade() -> None:
    # The correction is source-data based and intentionally not reversed.
    pass
