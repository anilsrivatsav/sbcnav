"""Classify unallotted catering units and separate tender receipts.

Revision ID: 0017_available_catering_units
Revises: 0016_catering_sheet_sync
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_available_catering_units"
down_revision = "0016_catering_sheet_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("units", sa.Column("remarks", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE units
        SET remarks = NULLIF(BTRIM(unit_status), ''),
            unit_status = 'Available'
        WHERE COALESCE(BTRIM(licensee_name), '') = ''
          AND COALESCE(BTRIM(contract_from), '') = ''
          AND COALESCE(BTRIM(contract_to), '') = ''
        """
    )
    op.execute(
        """
        UPDATE earnings AS e
        SET earning_scope = 'tender_emd'
        FROM units AS u
        WHERE e.unit_no = u.unit_no
          AND u.unit_status = 'Available'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE earnings
        SET earning_scope = 'unit'
        WHERE earning_scope = 'tender_emd'
        """
    )
    op.drop_column("units", "remarks")
