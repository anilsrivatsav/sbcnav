"""Versioned SBC monthly MCDO reports and dated asset positions."""
from alembic import op
import sqlalchemy as sa

revision = '0035_mcdo_monthly'
down_revision = '0034_auction_schedule'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('mcdo_monthly_periods',
        sa.Column('period', sa.String(7), primary_key=True),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('mcdo_monthly_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('period', sa.String(7), sa.ForeignKey('mcdo_monthly_periods.period'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('workbook', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('period', 'version'))
    op.create_index('ix_mcdo_monthly_versions_period', 'mcdo_monthly_versions', ['period'])


def downgrade():
    op.drop_table('mcdo_monthly_versions')
    op.drop_table('mcdo_monthly_periods')
