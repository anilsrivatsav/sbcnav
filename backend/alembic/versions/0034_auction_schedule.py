"""Shared auction holidays and Deskflow schedule links."""
from alembic import op
import sqlalchemy as sa

revision = '0034_auction_schedule'
down_revision = '0033_deskflow_workbook_archive'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('auction_holidays',
        sa.Column('day', sa.Date(), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False))
    op.create_table('auction_schedule_links',
        sa.Column('sync_id', sa.String(36), primary_key=True),
        sa.Column('lot_key', sa.String(512)),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('auction_date', sa.Date(), nullable=False),
        sa.Column('schedule_id', sa.String(100), nullable=False),
        sa.Column('catalogue_id', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('sheet_tab', sa.String(100), nullable=False),
        sa.Column('sheet_row', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_auction_schedule_links_lot_key', 'auction_schedule_links', ['lot_key'])

def downgrade():
    op.drop_index('ix_auction_schedule_links_lot_key', table_name='auction_schedule_links')
    op.drop_table('auction_schedule_links')
    op.drop_table('auction_holidays')
