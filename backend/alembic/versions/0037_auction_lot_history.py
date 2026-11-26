"""Persist observed auction schedules and associated RP review snapshots."""
from alembic import op
import sqlalchemy as sa

revision = '0037_auction_lot_history'
down_revision = '0036_contract_lifecycle'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'auction_lot_history',
        sa.Column('catalogue', sa.String(160), primary_key=True),
        sa.Column('lot', sa.String(200), primary_key=True),
        sa.Column('auction_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('schedule', sa.JSON(), nullable=False),
        sa.Column('review', sa.JSON(), nullable=False),
        sa.Column('events', sa.JSON(), nullable=False),
    )
    op.create_index('ix_auction_lot_history_auction_at', 'auction_lot_history', ['auction_at'])


def downgrade():
    op.drop_table('auction_lot_history')
