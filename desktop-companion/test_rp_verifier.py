import unittest
from dataclasses import asdict
from datetime import date

from rp.rules import calculate
from rp.verifier import verify


TODAY = date(2026, 10, 19)


def case(status='Running'):
    lot = {'lot': 'A-12', 'status': 'RP Pending', 'start': '2026-10-30',
           'rate_unit': 'Annual Licensing Fee'}
    auctions = [{'date': '2026-10-01', 'outcome': 'Sold', 'source': 'IREPS',
                 'awardee': 'Example contractor', 'bid_rate': '1000.00',
                 'rate_unit': 'Annual Licensing Fee', 'catalogue': 'C1', 'previous_lot': 'A-12'}]
    contract = {'status': status, 'source': 'IREPS', 'awardee': 'Example contractor',
                'rate_unit': 'Annual Licensing Fee', 'award_date': '2026-10-02',
                'start': '2026-10-03', 'end': '2026-10-29', 'lar': '1000'}
    inputs = {'family': 'Parking / Pay & Use', 'benchmark_source': 'IREPS',
              'identity_verified': True, 'conditions_reviewed': True}
    record = {'key': 'lot-1', 'revision': 'revision-1', 'lot': lot, 'auctions': auctions,
              'contract': contract, 'inputs': inputs,
              'result': asdict(calculate(lot, auctions, contract, inputs))}
    scheduled = {'ids': ['lot-1'], 'count': 1, 'complete': True, 'collected_at': '2026-10-19T10:00:00'}
    history = {'complete': True, 'from_date': '2023-01-01', 'to_date': '2026-10-19',
               'collected_at': '2026-10-19T10:05:00'}
    workbook = {'revision': 'revision-1', 'ready': True, 'workbook': 'Book.xlsx',
                'digest': 'hash-1', 'current_digest': 'hash-1'}
    return record, scheduled, history, workbook


class VerifierTests(unittest.TestCase):
    def report(self, record, scheduled, history, workbook):
        return verify(record, scheduled, history, workbook, today=TODAY)

    def test_running_lar_evidence_is_verified(self):
        report = self.report(*case())
        self.assertEqual(report['status'], 'verified', report['checks'])
        self.assertIn('10 days', next(c['message'] for c in report['checks'] if c['code'] == 'contract_period'))

    def test_completed_contract_requires_lar_plus_ten_percent(self):
        record, scheduled, history, workbook = case('Completed')
        record['contract']['end'] = '2026-10-18'
        self.assertEqual(record['result']['rp'], '1100.00')
        self.assertEqual(self.report(record, scheduled, history, workbook)['status'], 'verified')
        record['result']['rp'] = '1000.00'
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'calculation'), 'fail')

    def test_completed_contract_with_future_end_is_blocked(self):
        report = self.report(*case('Completed'))
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'contract_period'), 'fail')

    def test_invalid_auction_date_is_blocked(self):
        record, scheduled, history, workbook = case()
        record['auctions'][0]['date'] = '2026-99-99'
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'auction_evidence'), 'fail')

    def test_late_auction_and_stale_history_are_reported(self):
        record, scheduled, history, workbook = case()
        record['auctions'][0]['date'] = '2026-10-31'
        history['to_date'] = '2026-10-17'
        report = self.report(record, scheduled, history, workbook)
        states = {c['code']: c['state'] for c in report['checks']}
        self.assertEqual(states['auction_evidence'], 'fail')
        self.assertEqual(states['history_coverage'], 'warn')

    def test_future_earlier_auction_is_blocked_even_before_scheduled_date(self):
        record, scheduled, history, workbook = case()
        record['auctions'][0]['date'] = '2026-10-20'
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'auction_evidence'), 'fail')

    def test_rejected_bid_without_source_is_blocked(self):
        record, scheduled, history, workbook = case()
        record['auctions'].append({'date': '2026-10-10', 'outcome': 'Rejected', 'source': 'IREPS',
                                   'bid_rate': '900', 'rate_unit': 'Annual Licensing Fee',
                                   'catalogue': 'C2', 'previous_lot': 'A-12'})
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'rejected_bids'), 'fail')
        record['auctions'][1]['bid_source'] = 'IREPS bid view'
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'rejected_bids'), 'pass')

    def test_rejected_outcome_without_bid_needs_review(self):
        record, scheduled, history, workbook = case()
        record['auctions'].append({'date': '2026-10-10', 'outcome': 'Rejected', 'source': 'IREPS',
                                   'catalogue': 'C2', 'previous_lot': 'A-12'})
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'rejected_bids'), 'warn')

    def test_changed_workbook_requires_review(self):
        record, scheduled, history, workbook = case()
        workbook['current_digest'] = 'changed'
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(report['status'], 'needs_review')
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'local_workbook'), 'warn')

    def test_expired_running_contract_is_blocked(self):
        record, scheduled, history, workbook = case()
        record['contract']['end'] = '2026-10-18'
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'contract_period'), 'fail')

    def test_contract_end_before_start_is_blocked(self):
        record, scheduled, history, workbook = case('Completed')
        record['contract']['end'] = '2026-10-02'
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'contract_period'), 'fail')

    def test_foreclosure_before_commencement_is_blocked(self):
        record, scheduled, history, workbook = case('Foreclosed')
        record['contract']['closed'] = '2026-10-02'
        record['contract']['termination_source'] = 'IREPS decision'
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'foreclosure'), 'fail')

    def test_pricing_basis_rejects_arithmetically_consistent_wrong_benchmark(self):
        record, scheduled, history, workbook = case()
        record['auctions'] = []
        record['contract'] = {}
        record['inputs'] = {'family': 'Publicity', 'benchmark_source': 'Approved tariff',
                            'initial_rp': '1000', 'new_asset': True,
                            'identity_verified': True, 'conditions_reviewed': True}
        record['result'] = asdict(calculate(record['lot'], [], {}, record['inputs']))
        record['result']['base'] = '1200.00'
        record['result']['rp'] = '1200.00'
        record['result']['justification'] = 'Approved tariff supports proposed RP 1200.00.'
        report = self.report(record, scheduled, history, workbook)
        states = {c['code']: c['state'] for c in report['checks']}
        self.assertEqual(states['calculation'], 'pass')
        self.assertEqual(states['pricing_basis'], 'fail')

    def test_collection_without_timestamp_cannot_pass_cutoff(self):
        record, scheduled, history, workbook = case()
        scheduled['collected_at'] = None
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'collection_cutoff'), 'fail')

    def test_previous_day_scheduled_collection_needs_review(self):
        record, scheduled, history, workbook = case()
        scheduled['collected_at'] = '2026-10-18T10:00:00'
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(report['status'], 'needs_review')
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'scheduled_freshness'), 'warn')

    def test_incomplete_schedule_count_is_blocked(self):
        record, scheduled, history, workbook = case()
        scheduled['count'] = 2
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'scheduled_collection'), 'fail')

    def test_history_cannot_claim_future_coverage(self):
        record, scheduled, history, workbook = case()
        history['collected_at'] = '2026-10-18T10:05:00'
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'history_coverage'), 'warn')

    def test_history_horizon_must_stop_at_review_cutoff(self):
        record, scheduled, history, workbook = case()
        history['to_date'] = '2026-10-20'
        report = self.report(record, scheduled, history, workbook)
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code'] == 'history_coverage'), 'warn')


if __name__ == '__main__':
    unittest.main()
