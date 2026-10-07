"""Durable MCDO source-sync previews and phase checkpoints."""
from alembic import op
import sqlalchemy as sa
revision = '0031_mcdo_sync'
down_revision = '0030_publicity_earnings'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('mcdo_sync_runs',
        sa.Column('run_id',sa.String(36),primary_key=True),
        sa.Column('state',sa.String(32),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('result',sa.JSON(),nullable=False),
        sa.Column('error',sa.Text()))

def downgrade():
    op.drop_table('mcdo_sync_runs')
