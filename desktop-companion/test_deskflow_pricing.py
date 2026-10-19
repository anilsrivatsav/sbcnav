import unittest

from rp.rules import calculate
from rp.contract_fields import contract_status


class DeskflowPricingTests(unittest.TestCase):
    def proposal(self, status, later_outcome=None, family='Parking / Pay & Use', contract_overrides=None, sold_date='2026-10-01'):
        lot = {'lot': 'A-12', 'status': 'RP Pending', 'start': '2026-10-30',
               'rate_unit': 'Annual Licensing Fee'}
        auctions = [{'date': sold_date, 'outcome': 'Sold', 'source': 'IREPS',
                     'awardee': 'Example contractor', 'bid_rate': '1000.00',
                     'rate_unit': 'Annual Licensing Fee'}]
        if later_outcome:
            auctions.append({'date': '2026-10-15', 'outcome': later_outcome,
                             'source': 'IREPS', 'rate_unit': 'Annual Licensing Fee'})
        contract = {'status': status, 'source': 'IREPS', 'awardee': 'Example contractor',
                    'rate_unit': 'Annual Licensing Fee', 'award_date': '2026-10-02',
                    'start': '2026-10-03', 'end': '2026-10-09', 'lar': '1000'}
        contract.update(contract_overrides or {})
        inputs = {'family': family, 'benchmark_source': 'IREPS',
                  'identity_verified': True}
        return calculate(lot, auctions, contract, inputs)

    def test_running_contract_uses_lar_even_after_few_days(self):
        result = self.proposal('Running')
        self.assertTrue(result.ready, result.missing)
        self.assertEqual(result.rp, '1000.00')
        self.assertEqual(result.rule, 'running_lar')

    def test_completed_contract_adds_ten_percent_even_for_short_term(self):
        result = self.proposal('Completed')
        self.assertTrue(result.ready, result.missing)
        self.assertEqual(result.rp, '1100.00')
        self.assertEqual(result.rule, 'completed_lar')
        self.assertIn('plus 10%', result.justification)

    def test_completed_contract_uses_increased_lar_as_first_failed_retry_base(self):
        result = self.proposal('Completed', 'No Bids')
        self.assertTrue(result.ready, result.missing)
        self.assertEqual(result.rp, '1100.00')

    def test_foreclosure_uses_lar_regardless_of_duration_or_family(self):
        cases = (
            ('Parking / Pay & Use', {'closed': '2026-10-08'}),
            ('Publicity', {'closed': '2026-10-08'}),
            ('Catering / MPS', {'closed': '2026-10-08'}),
            ('Food truck', {'closed': '2026-10-08'}),
            ('Parking / Pay & Use', {'award_date': '2026-01-02', 'start': '2026-01-03', 'end': '2026-08-08', 'closed': '2026-08-08'}),
        )
        for family, contract in cases:
            with self.subTest(family=family, closed=contract['closed']):
                sold_date = '2025-12-01' if contract['closed'] == '2026-08-08' else '2026-10-01'
                result = self.proposal('Foreclosed', family=family, contract_overrides=contract, sold_date=sold_date)
                self.assertTrue(result.ready, result.missing)
                self.assertEqual(result.rp, '1000.00')
                self.assertEqual(result.rule, 'foreclosed_lar')

    def test_foreclosure_after_failed_auction_still_uses_lar(self):
        result = self.proposal('Foreclosed', 'No Bids', contract_overrides={'closed': '2026-10-08'})
        self.assertTrue(result.ready, result.missing)
        self.assertEqual(result.rp, '1000.00')
        self.assertEqual(result.rule, 'foreclosed_lar')

    def test_ireps_foreclosure_status_variants(self):
        for raw_status in ('Foreclosed', 'Foreclosed after 6 months by party', 'Foreclosure by Railway'):
            with self.subTest(raw_status=raw_status):
                self.assertEqual(contract_status(raw_status), 'Foreclosed')


if __name__ == '__main__':
    unittest.main()
