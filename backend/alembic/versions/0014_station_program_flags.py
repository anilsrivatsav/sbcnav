"""Add explicit ABSS and station redevelopment flags."""

from alembic import op
import sqlalchemy as sa


revision = "0014_station_program_flags"
down_revision = "0013_inspection_evidence_notes"
branch_labels = None
depends_on = None


ABSS_CODES = (
    "KGI", "RMGM", "CPT", "MYA", "MWM", "TK", "GBB", "KJM", "WFD",
    "MLO", "BWT", "KPN", "HSRA", "DPJ", "DBU", "HUP", "SSPN", "SBGA",
    "CSDR",
)


def upgrade() -> None:
    op.add_column("stations", sa.Column("abss_flag", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("stations", sa.Column("redevelopment_flag", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_stations_abss_flag", "stations", ["abss_flag"])
    op.create_index("ix_stations_redevelopment_flag", "stations", ["redevelopment_flag"])
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE stations SET abss_flag = true WHERE station_code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": list(ABSS_CODES)},
    )
    bind.execute(sa.text("UPDATE stations SET redevelopment_flag = true WHERE station_code IN ('YPR', 'BNC')"))


def downgrade() -> None:
    op.drop_index("ix_stations_redevelopment_flag", table_name="stations")
    op.drop_index("ix_stations_abss_flag", table_name="stations")
    op.drop_column("stations", "redevelopment_flag")
    op.drop_column("stations", "abss_flag")
