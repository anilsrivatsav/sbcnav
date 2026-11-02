import tempfile
import unittest
from pathlib import Path
from rp.store import Store
from test_rp_verifier import case, TODAY
from rp.verifier import verify


class HistoryRefreshTests(unittest.TestCase):
    def test_outcome_only_refresh_retains_separately_sourced_rate(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'evidence.sqlite')
            old={'outcome':'Sold','rate_unit':'Annual Licensing Fee','bid_rate':'1234.50',
                 'bid_source':'original viewer','awardee':'Verified awardee','date':'2026-10-01'}
            store.save_evidence('lot','auction',old,'date|catalogue|lot')
            store.save_evidence('lot','auction',{'outcome':'Sold','rate_unit':'Annual Licensing Fee',
                'captured':True,'awardee':'','bid_details_unavailable':'No viewer'},'date|catalogue|lot')
            new=store.evidence('lot','auction')[0]
            self.assertEqual(new['bid_rate'],'1234.50')
            self.assertEqual(new['awardee'],'Verified awardee')
            self.assertEqual(new['bid_source'],'original viewer')
            self.assertTrue(new['bid_details_unavailable'])

    def test_missing_viewer_stays_visible_to_verification(self):
        record,scheduled,history,workbook=case()
        record['auctions'][0]['bid_details_unavailable']='No viewer'
        report=verify(record,scheduled,history,workbook,today=TODAY)
        self.assertEqual(report['status'],'needs_review')
        self.assertEqual(next(c['state'] for c in report['checks'] if c['code']=='bid_refresh'),'warn')

if __name__=='__main__':unittest.main()
