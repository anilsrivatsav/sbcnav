import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from auction_lot_review import list_lots, record_lots

from models import AuctionLotHistory

START = '2026-11-23T11:00:00+05:30'
CHECKED = '2026-11-20T10:00:00+05:30'
LOT = {
    'catalogue': 'SBC-PRL-1019-26', 'lot': '22366-SLR-F2-SMVB-DNR-26-1',
    'start': START, 'category': 'Parcel - SLR', 'description': 'Front SLR lot'
}


class AuctionLotReviewTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        AuctionLotHistory.__table__.create(self.engine)
        self.addCleanup(self.engine.dispose)

    def sync(self, lots, overview=None, stamp=CHECKED):
        published = {'checked_at': stamp, 'lots': lots}
        now = datetime.fromisoformat(stamp)
        with Session(self.engine) as session, session.begin():
            record_lots(session, published, overview or {}, now)
        return published

    def read(self, published, now=CHECKED, month=None):
        with Session(self.engine) as session:
            return list_lots(session, published, month, datetime.fromisoformat(now))['lots']

    def review(self, **changes):
        checks = [{'code': code, 'state': 'pass'} for code in
                  ('scheduled_collection', 'history_coverage', 'calculation', 'pricing_basis', 'justification')]
        lot = {
            **LOT, 'rate_unit': 'Per Trip', 'verification': {'checks': checks},
            'proposal': {'revision': 'known-revision', 'status': 'ready_for_review', 'value': '37786',
                         'justification': 'Verified rate and source.'},
        }
        return {'collected_at': CHECKED, 'lots': [{**lot, **changes}]}

    def test_repeat_refresh_and_review_preserve_one_timeline(self):
        published = self.sync([LOT], self.review())
        self.sync([LOT], self.review())
        [lot] = self.read(published)
        self.assertEqual(lot['status'], 'ready')
        self.assertEqual([event['kind'] for event in lot['events']], ['schedule', 'review'])
        [stale] = self.read(published, '2026-11-21T09:00:00+05:30')
        self.assertEqual(stale['status'], 'pending')
        self.assertIn('Refresh', stale['reasons'][0])

    def test_reschedule_holds_the_old_proposal_and_keeps_original_event(self):
        self.sync([LOT], self.review())
        moved = {**LOT, 'start': '2026-11-23T15:00:00+05:30'}
        changed = self.sync([moved], self.review(), '2026-11-20T11:00:00+05:30')
        self.sync([moved], self.review(), '2026-11-20T11:00:00+05:30')
        [lot] = self.read(changed)
        self.assertEqual(lot['status'], 'pending')
        self.assertEqual(lot['review'], {})
        self.assertEqual([e['data']['start'] for e in lot['events'] if e['kind'] == 'schedule'],
                         [START, moved['start']])

    def test_empty_publish_preserves_november_and_catalogue_scopes_identity(self):
        other_catalogue = {**LOT, 'catalogue': 'SBC-PRL-1022-26'}
        published = self.sync([LOT, other_catalogue], self.review())
        self.assertEqual([lot['status'] for lot in self.read(published)], ['ready', 'pending'])
        empty = self.sync([], stamp='2026-11-24T10:00:00+05:30')
        self.assertEqual(self.read(empty), [])
        self.assertEqual(len(self.read(empty, '2026-11-24T10:00:00+05:30', month='2026-11')), 2)

    def test_missing_evidence_or_oversized_ireps_text_is_pending(self):
        pending = self.review(verification={'checks': [{'code': 'calculation', 'state': 'fail',
                                                        'message': 'Approved tariff missing.'}]})
        [lot] = self.read(self.sync([LOT], pending))
        self.assertIn('Approved tariff missing.', lot['reasons'])
        invalid = self.review()
        invalid['lots'][0]['proposal']['justification'] = 'x' * 301
        [lot] = self.read(self.sync([LOT], invalid))
        self.assertEqual(lot['status'], 'pending')
        self.assertTrue(any('300' in reason for reason in lot['reasons']))

    def test_legacy_date_only_rows_show_workbook_amount_without_replacing_ireps_time(self):
        entry = self.review(start=START[:10], proposal={'status': 'needs_evidence'},
                            workbook_source={'value': '37786', 'file': 'Parcel workbook.xlsx', 'row': 857})
        [lot] = self.read(self.sync([LOT], entry))
        self.assertEqual(lot['review']['workbook']['value'], '37786')
        self.assertEqual(lot['status'], 'pending')
        self.assertEqual(lot['start'], START)
        self.assertTrue(lot['time_known'])

        moved = {**LOT, 'start': '2026-11-23T15:00:00+05:30'}
        refreshed = '2026-11-20T11:00:00+05:30'
        [moved_lot] = self.read(self.sync([moved], entry, refreshed))
        self.assertEqual(moved_lot['review'], {})
        entry['collected_at'] = refreshed
        [rechecked] = self.read(self.sync([moved], entry, refreshed))
        self.assertEqual(rechecked['review']['workbook']['value'], '37786')
        self.assertEqual(rechecked['start'], moved['start'])

    def test_workbook_evidence_remains_visible_for_past_date_only_collections(self):
        entry = self.review(start=START[:10], workbook_source={'value': '37786'})
        now = '2026-11-26T10:00:00+05:30'
        published = self.sync([], entry, now)
        [lot] = self.read(published, now, month='2026-11')
        self.assertFalse(lot['time_known'])
        self.assertFalse(lot['current'])
        self.assertEqual(lot['review']['workbook']['value'], '37786')
