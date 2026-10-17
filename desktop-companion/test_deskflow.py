import tempfile, unittest
from pathlib import Path
from unittest.mock import Mock
from rp.standard_conditions import annual_fee
from rp.store import Store
from deskflow import Deskflow

class ConditionsTests(unittest.TestCase):
    def test_third_year_does_not_escalate(self):
        self.assertEqual(annual_fee('1000','2023-04-01','2028-03-31','2026-03-31'),'1000.00')
    def test_fourth_and_fifth_year_compound(self):
        self.assertEqual(annual_fee('1000','2023-04-01','2028-03-31','2026-04-01'),'1100.00')
        self.assertEqual(annual_fee('1000','2023-04-01','2028-03-31','2027-04-01'),'1210.00')
    def test_bot_and_romt_exception(self):
        for model in ('BOT','ROMT'):
            self.assertEqual(annual_fee('1000','2023-04-01','2038-03-31','2027-04-01',model),'1102.50')
    def test_no_fee_outside_contract(self):
        with self.assertRaises(ValueError):annual_fee('1000','2023-04-01','2026-03-31','2026-04-01')

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.d=object.__new__(Deskflow)
        import threading
        self.d.lock=threading.RLock();self.d.thread=None;self.d.store=Store(Path(self.temp.name)/'test.sqlite')
        self.d.previews={};self.d.userdir=Path(self.temp.name)
        self.key=self.d.store.save_lot({'catalogue':'C','lot':'L','start':'2026-11-01','status':'RP Pending','rate_unit':'Annual Licensing Fee'})
    def draft(self):
        d=self.d.detail(self.key)
        d['inputs']={'family':'Parking / Pay & Use','benchmark_source':'Approved benchmark fixture','initial_rp':'1000','new_asset':True,'identity_verified':True,'conditions_reviewed':True}
        return d
    def test_save_and_reload(self):
        result=self.d.save(self.draft());self.assertEqual(result['result']['rp'],'1000.00')
        self.assertIn('SCC v2.0',result['result']['justification'])
        self.assertEqual(self.d.detail(self.key)['result'],result['result'])
    def test_stale_review_rejected(self):
        old=self.draft();self.d.save(old)
        with self.assertRaisesRegex(ValueError,'Evidence changed'):self.d.save(old)
    def test_conditions_review_required(self):
        draft=self.draft();draft['inputs']['conditions_reviewed']=False
        self.assertFalse(self.d.save(draft)['result']['ready'])
    def test_progress_has_no_collected_records(self):
        self.d.updater=Mock();self.d.updater.snapshot.return_value={'busy':False}
        self.d.state={'phase':'ready','message':'Ready','error':None}
        self.assertEqual(set(self.d.progress()),{'phase','message','error','busy','updater_busy'})
    def test_pending_refresh_preserves_existing_value_and_is_idempotent(self):
        import shutil
        from rp.review import WorkbookPreview,cells
        from rp.rules import Result
        from rp.excel_io import _sheet_path,_strings,_text,Q
        import zipfile
        from lxml import etree as E
        target=Path(self.temp.name)/'commercial.xlsx';shutil.copy2('D:/ANIL/UK/Prk PnU.xlsx',target)
        with zipfile.ZipFile(target) as z:
            ss=_strings(z);root=E.fromstring(z.read(_sheet_path(z,'Table1')))
            for row in root.find(Q('sheetData')):
                cs={''.join(filter(str.isalpha,c.get('r'))):c for c in row}
                if int(row.get('r'))>5 and _text(cs.get('L'),ss) and _text(cs.get('N'),ss) and _text(cs.get('E'),ss):break
            lot={'lot':_text(cs['L'],ss),'catalogue':_text(cs['N'],ss),'rate_unit':_text(cs.get('G'),ss),'start':'2026-11-01'}
        before=cells(target,'Table1');address='E'+row.get('r')
        record={'lot':lot,'inputs':{'family':'Parking / Pay & Use'},'result':Result(False,missing='Verify contract termination date.')}
        for _ in range(2):
            p=WorkbookPreview(target,'commercial',[record],allow_existing=True,preserve_pending=True)
            p.commit();p.close()
        after=cells(target,'Table1')
        self.assertEqual(before[address],after[address])
        self.assertEqual(after['F'+row.get('r')].count('Deskflow update:'),1)
    def test_duplicate_and_future_auctions_rejected(self):
        draft=self.draft();row={'date':'2026-10-01','outcome':'No Bids','source':'fixture'};draft['auctions']=[row,dict(row)]
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.d.save(draft)
        draft['auctions']=[{**row,'date':'2026-11-02'}]
        with self.assertRaisesRegex(ValueError,'precede'):self.d.save(draft)
    def test_edit_replaces_old_evidence(self):
        draft=self.draft();draft['auctions']=[{'date':'2026-10-01','outcome':'No Bids','source':'fixture'}]
        draft=self.d.save(draft);draft['auctions']=[]
        self.assertEqual(self.d.save(draft)['auctions'],[])
    def test_cancellation_needs_actual_decision(self):
        draft=self.draft();draft['contract']={'status':'Not signed'}
        self.assertIn('decision',self.d.save(draft)['result']['missing'])
    def test_round_trip_site_label_is_a_rate_alias(self):
        from rp.rules import calculate
        draft=self.draft();draft['lot']['rate_unit']='Per Round Trip ( Two Way )'
        result=calculate(draft['lot'],[],{},draft['inputs'])
        self.assertTrue(result.ready);self.assertEqual(result.rp,'1000.00')
    def test_excel_preview_and_commit_preserve_other_cells(self):
        import shutil,json
        from rp.review import cells,digest
        target=Path(self.temp.name)/'commercial.xlsx';shutil.copy2('D:/ANIL/UK/Prk PnU.xlsx',target)
        (self.d.userdir/'workbooks.json').write_text(json.dumps({'commercial':str(target)}))
        draft=self.d.save(self.draft());before=digest(target);old=cells(target,'Table1')
        preview=self.d.excel('excel-preview',{'key':self.key,'revision':draft['revision']})
        self.assertEqual(before,digest(target));self.assertTrue(preview['changes'])
        self.d.excel('excel-save',{'preview_id':preview['preview_id']})
        after=cells(target,'Table1')
        for address,value in old.items():self.assertEqual(after[address],value)
        draft=self.d.detail(self.key);draft['inputs']['initial_rp']='1200';draft=self.d.save(draft)
        preview=self.d.excel('excel-preview',{'key':self.key,'revision':draft['revision']})
        self.assertTrue(any(c[0].startswith('R') and c[2]=='1200.0' for c in preview['changes']))
        self.d.excel('excel-save',{'preview_id':preview['preview_id']})
        import openpyxl
        book=openpyxl.load_workbook(target,read_only=True,data_only=True)
        self.assertEqual(list(book['Table1'].values)[-1][4],1200)
        book.close()
        with self.assertRaisesRegex(ValueError,'fresh'):self.d.excel('excel-save',{'preview_id':preview['preview_id']})
    def test_web_wording_is_neutral(self):
        from deskflow import public_text
        self.assertEqual(public_text({'message':'RP pending; reserve price','cells':[('E1','RP','RP 100')]}),{'message':'value pending; proposed value','cells':[['E1','value','value 100']]})
    def test_excel_download_has_live_formula_and_neutral_wording(self):
        import base64,io,re,openpyxl
        self.d.save(self.draft())
        output=self.d.excel('excel-export',{})
        raw=base64.b64decode(output['content'])
        book=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=False)
        self.assertTrue(book['Review']['F2'].value.startswith('='))
        self.assertFalse(any(re.search(r'\bRP\b',str(v)) for row in book['Review'].values for v in row if v is not None))
        book.close();book=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
        self.assertEqual(book['Review']['F2'].value,1000);book.close()
    def test_existing_user_row_changes_only_calculation_cells(self):
        import shutil,json
        from rp.review import cells
        target=Path(self.temp.name)/'commercial.xlsx';shutil.copy2('D:/ANIL/UK/Prk PnU.xlsx',target)
        before=cells(target,'Table1')
        row=next(str(n) for n in range(6,1650) if before.get('L'+str(n)) and before.get('N'+str(n)) and before.get('G'+str(n))=='Annual Licensing Fee')
        self.key=self.d.store.save_lot({'catalogue':before['N'+row],'lot':before['L'+row],'start':'2026-12-01','status':'RP Pending','rate_unit':'Annual Licensing Fee'})
        (self.d.userdir/'workbooks.json').write_text(json.dumps({'commercial':str(target)}))
        draft=self.d.save(self.draft());preview=self.d.excel('excel-preview',{'key':self.key,'revision':draft['revision']})
        self.assertTrue(all(c[0] in {col+row for col in ('E','F','R','S')} for c in preview['changes']))
        self.d.excel('excel-save',{'preview_id':preview['preview_id']})
        after=cells(target,'Table1')
        for address,value in before.items():
            if address not in {col+row for col in ('E','F','R','S')}:self.assertEqual(after[address],value)

if __name__=='__main__':unittest.main()
