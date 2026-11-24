from unittest import TestCase
from unittest.mock import patch

from ireps import IncompleteResultsError, Ireps


class DatePartitionTests(TestCase):
    def reader(self, *, date_column, outside=False):
        reader = Ireps.__new__(Ireps)
        reader.log = lambda _: None
        reader.check = lambda: None
        reader.navigate = lambda _: None
        windows = []

        def search(category, *, start, end, **filters):
            self.assertEqual('Catering', category)
            windows.append((start, end))

        def rows(mode, filtered=False):
            start, end = windows[-1]
            if (start, end) == ('21/11/2026', '24/11/2026'):
                raise IncompleteResultsError('IREPS repeated page 6.')
            cells = [''] * 9
            cells[date_column] = '25/11/2026' if outside else start
            return [{'cells': cells}]

        return reader, windows, search, rows

    def test_repeated_page_partitions_contract_creation_dates(self):
        reader, windows, search, rows = self.reader(date_column=1)
        with patch.object(reader, 'search', search), patch.object(reader, 'all_rows', rows):
            found = reader.read_category_rows('Contracts', 'Catering', 'contracts',
                                               start='21/11/2026', end='24/11/2026')
        self.assertEqual([('21/11/2026', '24/11/2026'), ('21/11/2026', '22/11/2026'),
                          ('23/11/2026', '24/11/2026')], windows)
        self.assertEqual(['21/11/2026', '23/11/2026'], [row['cells'][1] for row in found])

    def test_payment_partition_rejects_an_out_of_range_due_date(self):
        reader, _, search, rows = self.reader(date_column=7, outside=True)
        with patch.object(reader, 'search', search), patch.object(reader, 'all_rows', rows):
            with self.assertRaisesRegex(IncompleteResultsError, 'outside the selected date window'):
                reader.read_category_rows('Payments', 'Catering', 'paid',
                                          start='21/11/2026', end='24/11/2026')
