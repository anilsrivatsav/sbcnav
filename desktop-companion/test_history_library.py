import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from rp.store import Store
from rp.history_library import HistoryLibrary, day

def workbook(path, text='Old justification', value='45000'):
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="History" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/styles.xml',f'<styleSheet xmlns="{ns}"><cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>')
        z.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="{ns}"><sheetData><row r="9" hidden="1"><c r="A9" s="1"><v>{value}</v></c><c r="B9" t="inlineStr"><is><t>{text}</t></is></c><c r="C9"><f>2*3</f><v>6</v></c></row></sheetData></worksheet>')

class HistoryLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=Store(self.root/'library.sqlite');self.lib=HistoryLibrary(self.store)
    def event(self, lot='L', outcome='Sold', **extra):
        return {'catalogue':'C','lot':lot,'date':'2024-01-01','outcome':outcome,'source':'https://www.ireps.gov.in/catalogue','rate_unit':'Annual Licensing Fee',**extra}
    def scan(self):return self.lib.start_scan('2023-01-01','2024-12-31')
    def test_workbook_import_is_lossless_idempotent_and_keeps_versions(self):
        p=self.root/'book.xlsx';workbook(p);raw=p.read_bytes()
        report=self.lib.import_workbooks({'commercial':p})[0]
        self.assertEqual(p.read_bytes(),raw);self.assertEqual(report['rows'],1)
        row=self.lib.search_workbooks('Old justification')[0]
        self.assertEqual(row['sheet'],'History');self.assertEqual(row['row'],9)
        self.assertTrue(row['hidden']);self.assertEqual(row['cells']['C']['formula'],'2*3')
        self.assertEqual(row['cells']['C']['value'],'6');self.assertTrue(row['cells']['A']['date'].startswith('2023-'))
        self.lib.import_workbooks({'commercial':p})
        with self.store.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM df_workbook_rows').fetchone()[0],1)
        workbook(p,'Updated justification');self.lib.import_workbooks({'commercial':p})
        self.assertFalse(self.lib.search_workbooks('Old justification'))
        with self.store.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM df_workbook_rows').fetchone()[0],2)
    def test_catalogue_commits_survive_an_interruption(self):
        scan=self.scan();self.lib.save_catalogue(scan,'C','listing-v1',[self.event(bid_rate=100)])
        self.lib.scan_progress(scan,{'visited':['C'],'expected':2},interrupted=True)
        other=HistoryLibrary(Store(self.store.path))
        self.assertEqual(other.known_catalogues(),{'C':'listing-v1'})
        self.assertEqual(other.status()['auction_records'],1)
        with self.assertRaisesRegex(ValueError,'Incomplete'):other.finish_scan(scan,{'complete':True,'expected':2,'visited':['C']})
        self.assertFalse(other.coverage()['complete'])
    def test_catalogue_transaction_rolls_back_bad_rows(self):
        scan=self.scan();self.lib.save_catalogue(scan,'C','v1',[self.event()])
        with self.assertRaises(ValueError):self.lib.save_catalogue(scan,'C','v2',[self.event(lot='B',date='')])
        self.assertEqual(self.lib.known_catalogues()['C'],'v1')
        self.assertEqual(len(self.lib.auctions_for({'lot':'L','start':'2025-01-01'})),1)
    def test_sourced_bid_details_survive_a_metadata_refresh(self):
        scan=self.scan();self.lib.save_catalogue(scan,'C','v1',[self.event(bid_rate=100,awardee='Firm',bid_source='source')])
        self.lib.save_catalogue(scan,'C','v2',[self.event()])
        event=self.lib.auctions_for({'lot':'L','start':'2025-01-01'})[0]
        self.assertEqual(event['bid_rate'],100);self.assertEqual(event['awardee'],'Firm')
        self.lib.save_catalogue(scan,'C','v3',[self.event(outcome='Withdrawn')])
        self.assertNotIn('bid_rate',self.lib.auctions_for({'lot':'L','start':'2025-01-01'})[0])
        with self.store.connect() as c:self.assertGreaterEqual(c.execute('SELECT count(*) FROM df_auction_versions').fetchone()[0],2)
    def test_changed_code_requires_verified_scope_link(self):
        scan=self.scan();self.lib.save_catalogue(scan,'C','v1',[self.event(lot='OLD')])
        lot={'lot':'NEW','description':'Exact asset','rate_unit':'Annual Licensing Fee','start':'2025-01-01'}
        self.assertEqual(self.lib.auctions_for(lot),[])
        with self.assertRaises(ValueError):self.lib.link_asset(lot,'OLD','')
        with self.assertRaises(ValueError):self.lib.link_asset(lot,'NOT-COLLECTED','Scope document')
        self.lib.link_asset(lot,'OLD','Verified catalogue and scope document')
        self.assertEqual(self.lib.auctions_for(lot)[0]['previous_lot'],'OLD')
        self.assertEqual(self.lib.auctions_for({**lot,'description':'Larger asset'}),[])
    def test_exact_code_matches_without_similarity_inference(self):
        scan=self.scan();self.lib.save_catalogue(scan,'C','v1',[self.event(lot='LOT-1')])
        self.assertEqual(len(self.lib.auctions_for({'lot':'lot-1','start':'2025-01-01'})),1)
        self.assertEqual(self.lib.auctions_for({'lot':'LOT-10','start':'2025-01-01'}),[])
    def test_proposal_review_binds_revision_and_workbook(self):
        p=self.lib.proposal('K','evidence-a',{'ready':True,'rp':'100'})
        self.assertEqual(p['status'],'ready_for_review')
        self.lib.review_proposal('K',p['revision'],{'commercial':'hash-a'})
        self.assertEqual(self.lib.proposal('K','evidence-a',{'ready':True,'rp':'100'})['status'],'reviewed')
        self.lib.mark_saved('K',p['revision'])
        changed=self.lib.proposal('K','evidence-b',{'ready':True,'rp':'110'})
        self.assertEqual(changed['status'],'ready_for_review')
        with self.assertRaises(ValueError):self.lib.review_proposal('K',p['revision'])
        with self.assertRaises(ValueError):self.lib.mark_saved('K',changed['revision'])
    def test_pending_proposal_cannot_be_reviewed(self):
        p=self.lib.proposal('K','a',{'ready':False,'missing':'Policy source'})
        with self.assertRaises(ValueError):self.lib.review_proposal('K',p['revision'])
    def test_old_partial_metadata_does_not_claim_coverage(self):
        self.store.save_evidence('__workspace__','workbook_ireps_history',{'rows':[self.event()],'complete':True})
        self.lib.migrate_evidence();self.assertEqual(self.lib.status()['auction_records'],1)
        self.assertEqual(self.lib.known_catalogues(),{});self.assertTrue(self.lib.history_plan()['initial'])
        scan=self.scan();self.lib.save_catalogue(scan,'C','new',[self.event(outcome='Rejected')])
        self.lib.migrate_evidence()
        self.assertEqual(self.lib.auctions_for({'lot':'L','start':'2025-01-01'})[0]['outcome'],'Rejected')
    def test_incomplete_or_gapped_ranges_never_claim_global_completion(self):
        s=self.lib.start_scan('2024-01-01','2024-12-31')
        self.lib.finish_scan(s,{'complete':True,'expected':0,'visited':[]})
        self.assertFalse(self.lib.coverage()['complete']);self.assertTrue(self.lib.history_plan()['initial'])
    def test_existing_workspace_is_preserved(self):
        self.store.save_lot({'lot':'L','catalogue':'C'})
        HistoryLibrary(self.store)
        self.assertEqual(len(self.store.lots()),1)
    def test_delayed_outcomes_remain_due_outside_recent_window(self):
        self.store.save_lot({'catalogue':'C','lot':'L','start':'2023-01-01'})
        # A later schedule snapshot no longer includes the old lot.
        self.store.save_evidence('__workspace__','scheduled_snapshot',{'ids':[]})
        scan=self.lib.start_scan('2022-01-01','2025-01-01')
        self.lib.finish_scan(scan,{'complete':True,'expected':0,'visited':[]})
        plan=self.lib.history_plan('2025-02-01')
        self.assertEqual(plan['from_date'],'2023-01-01')
        self.assertEqual(plan['force_catalogues'],['C'])
        self.lib.save_catalogue(scan,'C','pending',[self.event(date='2023-01-01',outcome='Unknown')])
        self.assertEqual(len(self.lib.outcome_followups()),1)
        self.lib.save_catalogue(scan,'C','final',[self.event(date='2023-01-01',outcome='Rejected')])
        self.assertEqual(self.lib.outcome_followups(),[])
        self.assertEqual(self.lib.history_plan('2025-02-01')['force_catalogues'],[])
    def test_future_auction_is_not_due_until_auction_date(self):
        self.store.save_lot({'catalogue':'F','lot':'L','start':'2025-03-01'})
        self.assertEqual(len(self.lib.outcome_followups()),1)
        self.assertEqual(self.lib.history_plan('2025-02-01')['force_catalogues'],[])
        self.assertEqual(self.lib.history_plan('2025-03-01')['force_catalogues'],['F'])
    def test_bid_enrichment_targets_relevant_codes_and_verified_links(self):
        scan=self.scan()
        self.lib.save_catalogue(scan,'C','v1',[self.event(lot='OLD'),self.event(lot='UNRELATED'),self.event(lot='UNAVAILABLE',bid_details_unavailable=True)])
        lot={'lot':'NEW','description':'Asset','start':'2025-01-01'}
        self.assertEqual(self.lib.bid_enrichment_plan([lot])['force_catalogues'],[])
        self.lib.link_asset(lot,'OLD','Verified scope')
        plan=self.lib.bid_enrichment_plan([lot])
        self.assertEqual(plan['force_catalogues'],['C'])
        self.assertEqual(plan['detail_lots'],['NEW','OLD'])
        self.assertEqual(self.lib.bid_enrichment_plan([{'lot':'UNAVAILABLE','start':'2025-01-01'}])['force_catalogues'],[])

if __name__=='__main__':unittest.main()
