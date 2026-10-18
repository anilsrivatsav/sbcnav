"""Encrypted Deskflow workbook archive."""
from alembic import op
import sqlalchemy as sa

revision = '0033_deskflow_workbook_archive'
down_revision = '0032_deskflow_relay'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('deskflow_workbook_archive',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ciphertext', sa.Text(), nullable=False))


def downgrade():
    op.drop_table('deskflow_workbook_archive')
