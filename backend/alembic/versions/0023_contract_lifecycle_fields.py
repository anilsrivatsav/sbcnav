"""Add contract lifecycle and security-deposit fields.

Revision ID: 0023_contract_lifecycle_fields
Revises: 0022_work_progress_photos
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_contract_lifecycle_fields"
down_revision = "0022_work_progress_photos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("commercial_contracts")}
    for name, column in {
        "security_deposit": sa.Integer(),
        "renewal_status": sa.Text(),
        "termination_status": sa.Text(),
        "tender_status": sa.Text(),
    }.items():
        if name not in existing:
            op.add_column("commercial_contracts", sa.Column(name, column, nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes("commercial_contracts")}
    for name, column in {
        "ix_commercial_contracts_security_deposit": "security_deposit",
        "ix_commercial_contracts_renewal_status": "renewal_status",
        "ix_commercial_contracts_termination_status": "termination_status",
        "ix_commercial_contracts_tender_status": "tender_status",
    }.items():
        if name not in indexes:
            op.create_index(name, "commercial_contracts", [column])


def downgrade() -> None:
    op.drop_index("ix_commercial_contracts_tender_status", table_name="commercial_contracts")
    op.drop_index("ix_commercial_contracts_termination_status", table_name="commercial_contracts")
    op.drop_index("ix_commercial_contracts_renewal_status", table_name="commercial_contracts")
    op.drop_index("ix_commercial_contracts_security_deposit", table_name="commercial_contracts")
    op.drop_column("commercial_contracts", "tender_status")
    op.drop_column("commercial_contracts", "termination_status")
    op.drop_column("commercial_contracts", "renewal_status")
    op.drop_column("commercial_contracts", "security_deposit")
