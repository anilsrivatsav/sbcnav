"""Canonical contracts, retained lifecycle evidence, and linked invoice accounts."""
from alembic import op
import sqlalchemy as sa

revision = '0036_contract_lifecycle'
down_revision = '0035_mcdo_monthly'
branch_labels = None
depends_on = None


def upgrade():
    for column in (
        sa.Column('canonical_contract_id', sa.Integer(), nullable=True),
        sa.Column('source_present', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('ireps_status', sa.String(128)),
        sa.Column('ireps_checked_at', sa.DateTime(timezone=True)),
        sa.Column('lifecycle_verified_at', sa.DateTime(timezone=True)),
        sa.Column('status_effective_date', sa.Date()),
        sa.Column('reconciliation_state', sa.String(32), nullable=False, server_default='unverified'),
        sa.Column('reconciliation_issues', sa.JSON(), nullable=False, server_default='[]')):
        op.add_column('contract_registry_contracts', column)
    op.create_foreign_key('fk_contract_canonical', 'contract_registry_contracts',
                         'contract_registry_contracts', ['canonical_contract_id'], ['contract_id'], ondelete='RESTRICT')
    op.create_index('ix_contract_canonical', 'contract_registry_contracts', ['canonical_contract_id'])
    for column in (
        sa.Column('charge_type', sa.String(64)), sa.Column('frequency', sa.String(64)),
        sa.Column('period_start', sa.Date()), sa.Column('period_end', sa.Date()),
        sa.Column('source_reference', sa.Text()),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default=sa.true())):
        op.add_column('contract_registry_payment_schedules', column)
    for column in (
        sa.Column('receipt_key', sa.String(128)), sa.Column('invoice_number', sa.String(128)),
        sa.Column('due_date', sa.Date()), sa.Column('gst_amount', sa.Numeric(14,2)),
        sa.Column('penalty_amount', sa.Numeric(14,2)), sa.Column('gross_amount', sa.Numeric(14,2)),
        sa.Column('verification_status', sa.String(32), nullable=False, server_default='unverified')):
        op.add_column('contract_registry_payments', column)
    op.create_index('uq_registry_receipt_key', 'contract_registry_payments', ['receipt_key'], unique=True)
    op.create_table('contract_registry_evidence',
        sa.Column('evidence_id',sa.String(64),primary_key=True),
        sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_registry_contracts.contract_id',ondelete='RESTRICT'),nullable=False,index=True),
        sa.Column('source',sa.String(128),nullable=False),
        sa.Column('checked_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('sha256',sa.String(64),nullable=False),sa.Column('content',sa.JSON(),nullable=False))
    op.create_table('contract_registry_events',
        sa.Column('event_id',sa.String(64),primary_key=True),
        sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_registry_contracts.contract_id',ondelete='RESTRICT'),nullable=False,index=True),
        sa.Column('event_type',sa.String(64),nullable=False,index=True),sa.Column('effective_date',sa.Date()),
        sa.Column('observed_at',sa.DateTime(timezone=True),nullable=False),sa.Column('reason',sa.Text()),
        sa.Column('source_reference',sa.Text(),nullable=False),
        sa.Column('evidence_id',sa.String(64),sa.ForeignKey('contract_registry_evidence.evidence_id',ondelete='RESTRICT')))
    op.create_table('contract_registry_issues',
        sa.Column('issue_id',sa.String(64),primary_key=True),
        sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_registry_contracts.contract_id',ondelete='RESTRICT'),index=True),
        sa.Column('code',sa.String(64),nullable=False,index=True),sa.Column('detail',sa.JSON(),nullable=False),
        sa.Column('opened_at',sa.DateTime(timezone=True),nullable=False),sa.Column('last_seen_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('resolved_at',sa.DateTime(timezone=True)))


def downgrade():
    # Reverting the application image is supported. Retain financial/evidence
    # data instead of offering a downgrade that silently drops audit history.
    raise RuntimeError('Contract lifecycle downgrade requires an explicit backed-up data migration.')
