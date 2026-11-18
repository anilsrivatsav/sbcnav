import copy
import os
os.environ.setdefault('DATABASE_URL', 'sqlite+pysqlite:///:memory:')
import unittest
from datetime import date, datetime, timezone
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from database import Base
from models import (ContractRegistryContract as Contract, ContractRegistryPayment as Payment,
                    ContractRegistryEvent as Event, ContractRegistryPaymentSchedule as Schedule,
                    PublicityEarningsImport, PublicityEarningsCurrent, PublicityEarning)
from contract_lifecycle import CATEGORIES, reconcile, lifecycle, visible_status, validate_evidence


def evidence():
    return dict(collection_complete=True, asof='17/11/2026', completed_categories=CATEGORIES,
                completed_payment_categories=CATEGORIES, contracts=[dict(contract='SBC-RDN-KPN-26',
                firm='Example Ltd', start='01/01/2026', end='31/12/2030', status='Cancelled',
                contract_date='01/01/2026', category='Misc-Static-Services')], details={},
                payments=[dict(invoice='ES26TEST1', contract='SBC-RDN-KPN-26',
                               paid='2026-09-01', total='118.00', due='01/09/2026')])


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_cancellation_not_inferred_to_be_termination_and_clause_is_ignored(self):
        result = lifecycle({'status': 'Cancelled'}, {'fields': [], 'text': 'may be terminated for non payment'})
        self.assertEqual(result['status'], 'cancelled')
        self.assertIsNone(result['effective'])
        self.assertIn('closure_effective_date_missing', result['issues'])

    def test_labelled_foreclosure_date_is_retained(self):
        result = lifecycle({'status': 'Cancelled'}, {'fields': [
            ['Foreclosure Date:', '12/09/2026'], ['Foreclosure Reason:', 'Licensee request'],
            ['Foreclosure Order Number:', 'ORDER/7']]})
        self.assertEqual(result['status'], 'foreclosed')
        self.assertEqual(result['effective'], date(2026, 9, 12))
        self.assertEqual(result['reason'], 'Licensee request')

    def test_running_requires_current_period_and_official_check(self):
        c = Contract(status='running', source_present=True, period_start=date(2026, 1, 1),
                     period_end=date(2026, 9, 1))
        self.assertEqual(visible_status(c, date(2026, 11, 17)), 'expiry_review')
        c.period_end = date(2030, 1, 1)
        self.assertEqual(visible_status(c, date(2026, 11, 17)), 'verification_required')
        c.ireps_checked_at = datetime.now(timezone.utc)
        self.assertEqual(visible_status(c, date(2026, 11, 17)), 'running')

    def test_no_silent_reinstatement(self):
        self.assertEqual(lifecycle({'status': 'LIVE'}, {}, 'foreclosed')['status'], 'status_conflict')

    def test_incomplete_scan_is_rejected(self):
        e = evidence(); e['completed_categories'] = CATEGORIES[:7]
        with self.assertRaises(ValueError): validate_evidence(e)

    def test_alias_and_receipt_reconcile_idempotently(self):
        self.session.add(Contract(source_system='legacy_commercial', contract_number='commercial-103',
                                  contract_name='SBC-RDN-KPN-26', contract_family='station', status='running'))
        self.session.flush()
        e = evidence()
        e['details']['SBC-RDN-KPN-26'] = {'fields': [], 'schedule': [
            ['1', '', 'License Fee', 'Quarterly', '01/09/2026', '', '-', '-', '01/09/2026', '30/11/2026', 'Generated', 'No']]}
        result = reconcile(self.session, e); self.session.commit()
        self.assertEqual(result['counts']['aliases'], 1)
        self.assertEqual(result['counts']['rdn_linked_receipts'], 1)
        payment = self.session.scalar(select(Payment))
        schedule_id = payment.schedule_id
        self.assertIsNotNone(schedule_id)
        self.assertIsNone(payment.amount_paid)  # gross is not licence fee
        self.assertIsNone(self.session.get(Schedule, schedule_id).expected_amount)
        reconcile(self.session, e); self.session.commit()
        self.assertEqual(self.session.scalar(select(func.count()).select_from(Payment)), 1)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(Event)), 1)
        self.assertEqual(self.session.scalar(select(Payment)).schedule_id, schedule_id)
        self.assertEqual(self.session.scalar(select(Contract).where(Contract.source_system == 'e_auction')).status, 'cancelled')

    def test_ledger_fee_tax_and_penalty_remain_separate(self):
        self.session.add(PublicityEarningsImport(import_id='test', filename='test', row_count=1, warnings=[]))
        self.session.flush()
        self.session.add(PublicityEarningsCurrent(dataset='main', import_id='test'))
        self.session.add(PublicityEarning(import_id='test', source_row=2, financial_year='2026-27',
             receipt_date=date(2026,9,1), licence_fee=95, penalty=5, gst=18, total_with_gst=118,
             source_values={'Invoice':'ES26TEST1','Policy':'SBC-RDN-KPN-26'}))
        self.session.flush()
        reconcile(self.session, evidence()); self.session.commit()
        p = self.session.scalar(select(Payment))
        self.assertEqual(p.verification_status, 'ledger_matched')
        self.assertEqual(float(p.amount_paid), 95)
        self.assertEqual(float(p.gst_amount), 18)
        self.assertEqual(float(p.penalty_amount), 5)

    def test_conflicting_receipt_does_not_overwrite_original(self):
        reconcile(self.session, evidence()); self.session.commit()
        e = evidence(); e['payments'][0]['total'] = '999'
        result = reconcile(self.session, e); self.session.commit()
        self.assertEqual(float(self.session.scalar(select(Payment)).gross_amount), 118)
        self.assertEqual(result['counts']['receipt_exceptions'], 1)

    def test_missing_contract_is_retained_with_review_flag(self):
        reconcile(self.session, evidence()); self.session.commit()
        e = evidence(); e['contracts'][0]['contract'] = 'NEW'
        reconcile(self.session, e); self.session.commit()
        old = self.session.scalar(select(Contract).where(Contract.contract_number == 'SBC-RDN-KPN-26'))
        self.assertIsNotNone(old)
        self.assertFalse(old.source_present)
        self.assertEqual(old.status, 'cancelled')


if __name__ == '__main__': unittest.main()
