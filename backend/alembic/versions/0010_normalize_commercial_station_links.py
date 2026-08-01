"""normalize commercial station link labels

Revision ID: 0010_comm_station_links
Revises: 0009_commercial_contracts
Create Date: 2026-07-21 00:00:00.000000
"""

from alembic import op


revision = "0010_comm_station_links"
down_revision = "0009_commercial_contracts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE commercial_contracts
        SET station_match_status = 'Station linked'
        WHERE station_match_status IN ('direct_station', 'multi_station', 'inferred_from_contract_name')
        """
    )
    op.execute(
        """
        UPDATE commercial_contract_station_links
        SET match_status = 'Station linked',
            match_type = CASE
                WHEN match_type IN ('direct', 'multi_station') THEN 'station_link'
                WHEN match_type = 'inferred_from_contract_name' THEN 'station_inferred'
                ELSE match_type
            END
        WHERE station_code IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE commercial_contract_station_links
        SET match_status = 'Matched',
            match_type = CASE
                WHEN match_type = 'station_link' THEN 'direct'
                WHEN match_type = 'station_inferred' THEN 'inferred_from_contract_name'
                ELSE match_type
            END
        WHERE station_code IS NOT NULL
        """
    )
