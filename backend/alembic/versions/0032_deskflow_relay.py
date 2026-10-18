"""Deskflow desktop relay state."""
from alembic import op
import sqlalchemy as sa

revision = '0032_deskflow_relay'
down_revision = '0031_mcdo_sync'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('deskflow_relay',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('overview', sa.JSON(), nullable=False),
        sa.Column('software_update', sa.JSON(), nullable=False),
        sa.Column('command', sa.JSON(), nullable=False),
        sa.Column('command_id', sa.String(36)),
        sa.Column('last_seen_at', sa.DateTime(timezone=True)))

def downgrade():
    op.drop_table('deskflow_relay')
