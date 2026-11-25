from unittest import TestCase
from unittest.mock import Mock, patch
from playwright.sync_api import TimeoutError

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

        def rows(mode, filtered=False, max_rows=None):
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

    def test_undated_unsigned_contract_is_kept_once_across_windows(self):
        reader, _, search, rows = self.reader(date_column=1)
        unscheduled = {'cells':['SBC-AWARD-26','','','','','','','Pending for Sign (Bidder)','']}
        def included_rows(mode, filtered=False, max_rows=None):
            return rows(mode, filtered, max_rows) + [unscheduled]
        with patch.object(reader, 'search', search), patch.object(reader, 'all_rows', included_rows):
            found = reader.read_category_rows('Contracts', 'Catering', 'contracts',
                                               start='21/11/2026', end='24/11/2026')
        self.assertEqual(len(found), 3)
        self.assertEqual(found.count(unscheduled), 1)

    def test_dense_window_splits_before_touching_the_pager(self):
        reader = Ireps.__new__(Ireps)
        reader.page = Mock()
        reader.page.locator.return_value.inner_text.return_value = '71 Records Found'
        reader.page_rows = Mock()
        with self.assertRaisesRegex(IncompleteResultsError, 'split the search before paging'):
            reader.all_rows('contracts', max_rows=50)
        reader.page_rows.assert_not_called()

    def test_search_timeout_retries_the_same_window(self):
        reader = Ireps.__new__(Ireps)
        reader.check = Mock()
        reader.log = Mock()
        reader.navigate = Mock()
        reader.search = Mock(side_effect=[TimeoutError('Search took too long'), None])
        reader.all_rows = Mock(return_value=[])
        reader.read_category_rows('Contracts','Catering','contracts',start='08/01/2020',end='10/01/2020')
        reader.navigate.assert_called_once_with('Contracts')
        self.assertEqual(reader.search.call_args_list[0],reader.search.call_args_list[1])

    def test_subcategories_must_cover_the_parent_results(self):
        reader = Ireps.__new__(Ireps)
        reader.check = Mock()
        reader.log = Mock()
        reader.navigate = Mock()
        first, second = ({'cells':['first']},{'cells':['second']})
        reader.page_rows = Mock(return_value=[first])
        reader.read_category_rows = Mock(side_effect=[[first],[second]])
        self.assertEqual(reader.read_subcategories('Contracts','Catering',{},['101151','101152'],2),[first,second])
        reader.read_category_rows.side_effect = [[second],[second]]
        self.assertIsNone(reader.read_subcategories('Contracts','Catering',{},['101151','101152'],2))

    def test_routine_parking_uses_the_visible_radio_taxi_filter(self):
        reader = Ireps.__new__(Ireps)
        reader.page = Mock()
        control = reader.page.locator.return_value
        control.evaluate.return_value = [['Parking - General','1'],['Parking - Radio Taxi','2']]
        self.assertEqual(reader.receipt_filters('Parking'),{'subcategory':'2'})
        control.evaluate.return_value.append(['Radio Taxi (Other)','3'])
        self.assertEqual(reader.receipt_filters('Parking'),{})
