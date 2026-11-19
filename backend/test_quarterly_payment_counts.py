from os import environ
from types import SimpleNamespace
from unittest import TestCase

environ.setdefault('DATABASE_URL', 'sqlite+pysqlite:///:memory:')
from contract_registry import quarterly_payment_counts


class QuarterlyPaymentCountsTest(TestCase):
    def test_distinct_verified_paid_quarters(self):
        def schedule(number, frequency='Quarterly', charge_type='License Fee', status='Generated'):
            return SimpleNamespace(schedule_id=number, frequency=frequency, charge_type=charge_type,
                                   status=status, expected_amount=100, is_current=True)

        def receipt(number, amount=100, verification='ledger_matched'):
            return SimpleNamespace(schedule_id=number, amount_paid=amount, gross_amount=amount,
                                   payment_status='collected', verification_status=verification)

        schedules = [schedule(1), schedule(2), schedule(3, charge_type='Fine'),
                     schedule(4, frequency='Monthly'), schedule(5, status='Waived')]
        receipts = [receipt(1), receipt(1), receipt(2, amount=50), receipt(2, verification='ledger_mismatch'),
                    receipt(3), receipt(4), receipt(5), receipt(None)]
        self.assertEqual(quarterly_payment_counts(schedules, receipts),
                         {'quarters_scheduled': 3, 'quarters_paid': 1})
