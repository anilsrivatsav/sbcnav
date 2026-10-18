import unittest

from rp.rules import calculate


class DeskflowPricingTests(unittest.TestCase):
    def proposal(self, status, later_outcome=None):
        lot = {'lot': 'A-12', 'status': 'RP Pending', 'start': '2026-10-30',
               'rate_unit': 'Annual Licensing Fee'}
        auctions = [{'date': '2026-10-01', 'outcome': 'Sold', 'source': 'IREPS',
                     'awardee': 'Example contractor', 'bid_rate': '1000.00',
                     'rate_unit': 'Annual Licensing Fee'}]
        if later_outcome:
            auctions.append({'date': '2026-10-15', 'outcome': later_outcome,
                             'source': 'IREPS', 'rate_unit': 'Annual Licensing Fee'})
        contract = {'status': status, 'source': 'IREPS', 'awardee': 'Example contractor',
                    'rate_unit': 'Annual Licensing Fee', 'award_date': '2026-10-02',
                    'start': '2026-10-03', 'end': '2026-10-09', 'lar': '1000'}
        inputs = {'family': 'Parking / Pay & Use', 'benchmark_source': 'IREPS',
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


if __name__ == '__main__':
    unittest.main()
