import unittest
from rp.history_refresh import refresh_start, retry_connection


def covered():
    return {'complete':True,'reader_version':2,'from_date':'2023-01-01','to_date':'2026-10-27',
            'lot_codes':['A','B'],'coverage':{'complete':True,'expected':2,'visited':['C1','C2']}}


class RefreshTests(unittest.TestCase):
    def test_lost_connection_retries_are_bounded_and_respect_cancellation(self):
        message='page.evaluate: Target page, context or browser has been closed'
        self.assertTrue(retry_connection(message,0,False))
        self.assertFalse(retry_connection(message,3,False))
        self.assertFalse(retry_connection(message,0,True))
        self.assertFalse(retry_connection('Incomplete catalogue scan',0,False))

    def plan(self,previous,codes=('A',)):
        return refresh_start(previous,codes,'2023-01-01','2026-10-27')

    def test_verified_same_lots_recheck_thirty_days(self):
        self.assertEqual(self.plan(covered()),'2026-09-27')

    def test_new_lot_requires_full_history(self):
        self.assertIsNone(self.plan(covered(),['A','C']))

    def test_old_or_incomplete_scans_cannot_be_reused(self):
        for change in ({'reader_version':1},{'complete':False},{'lot_codes':[]},
                       {'from_date':'2026-10-01'},{'to_date':'2026-10-28'},
                       {'coverage':{'complete':True,'expected':3,'visited':['C1','C2']}},
                       {'coverage':{'complete':True,'expected':2,'visited':['C1','C1']}}):
            with self.subTest(change=change):
                self.assertIsNone(self.plan({**covered(),**change}))

    def test_incremental_refresh_retains_original_full_scan_proof(self):
        previous=covered();previous['baseline_coverage']=previous['coverage']
        previous['coverage']={'complete':True,'expected':1,'visited':['C3']}
        self.assertEqual(self.plan(previous),'2026-09-27')

    def test_failed_incremental_count_cannot_hide_behind_valid_baseline(self):
        previous=covered();previous['baseline_coverage']=previous['coverage']
        previous['coverage']={'complete':True,'expected':2,'visited':['C3']}
        self.assertIsNone(self.plan(previous))

if __name__=='__main__':unittest.main()
