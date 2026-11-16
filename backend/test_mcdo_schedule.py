"""Licence installment validation for mixed IREPS payment schedules."""
import unittest
from copy import deepcopy
from datetime import date
from mcdo.core import contract_terms


class ScheduleTests(unittest.TestCase):
    text = ('Contract No.\tSBC-Test-24\nRate (Rs.)\t7700000\n'
            'Contract Value\tRs. 27258000.00\n'
            'Contract Start Date\t10/11/2024\n'
            'Contract End Date\t09/11/2027\nContract Duration\t3 Years')

    def row(self, due, kind='License Fee', frequency='Quarterly', status='Generated'):
        return ['1', '01/01/2025', kind, frequency, due, due,
                '-', '-', '10/02/2025', '09/05/2025', status, 'No']

    def parse(self, rows):
        return contract_terms(self.text, rows, 'SBC-Test-24', 'Running')

    def test_one_time_fine_is_preserved_in_evidence_but_not_licence_dates(self):
        rows = [self.row('26/10/2025'), self.row('07/01/2026', 'Fine', 'One-time Payment'),
                self.row('26/01/2026', status='Waived by authority')]
        original = deepcopy(rows)
        result = self.parse(rows)
        self.assertEqual(result['dates'], [date(2025, 10, 26), date(2026, 1, 26)])
        self.assertEqual(result['waived_dates'], [date(2026, 1, 26)])
        self.assertEqual(rows, original)

    def test_unknown_or_nonquarterly_charges_still_stop_validation(self):
        for row in (self.row('26/01/2026', frequency='Monthly'),
                    self.row('26/01/2026', frequency='One-time Payment'),
                    self.row('26/01/2026', 'Unknown', 'One-time Payment'),
                    self.row('26/01/2026', 'Fine'), ['short']):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.parse([self.row('26/10/2025'), row])

    def test_empty_or_fine_only_schedule_still_stops_validation(self):
        for rows in ([], [self.row('07/01/2026', 'Fine', 'One-time Payment')]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.parse(rows)

    def test_duplicate_or_descending_licence_dates_still_stop_validation(self):
        for dues in (['26/01/2026', '26/01/2026'], ['26/01/2026', '26/10/2025']):
            with self.subTest(dues=dues), self.assertRaisesRegex(ValueError, 'strictly increasing'):
                self.parse([self.row(d) for d in dues])


if __name__ == '__main__':
    unittest.main()
