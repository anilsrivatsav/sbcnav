import os
os.environ.setdefault('DATABASE_URL','sqlite:///:memory:')
import unittest
from copy import deepcopy
from unittest.mock import patch
from datetime import date, datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
import mcdo_router as api
from models import McdoSyncRun, McdoMonthlyPeriod, McdoMonthlyVersion, PublicityEarningsCurrent, PublicityEarningsImport
from mcdo.core import cell, entered
from mcdo.sheets_api import computed_workbook
from openpyxl import load_workbook
from io import BytesIO

class FakeSheets:
    def __init__(self, grids):self.grids=deepcopy(grids);self.calls=[];self.fail_once=True;self.status={}
    def read(self,name,title=None,columns=None):
        if title:return {'grid':deepcopy(self.status.get(name,[]))}
        return {'properties':{'sheetId':1,'gridProperties':{'rowCount':10}},'grid':deepcopy(self.grids[name])}
    def patches(self,name,current,patches,formats,status):
        if name=='master' and self.fail_once:self.fail_once=False;raise RuntimeError('Second sheet unavailable')
        self.calls.append((name,deepcopy(patches)))
        from mcdo.checkpoint import planned_grid
        self.grids[name]=planned_grid(self.grids[name],patches,api.SOURCES[name]['columns'])
        self.status[name]=deepcopy(status)

class McdoTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite:///:memory:')
        for model in (McdoSyncRun, McdoMonthlyPeriod, McdoMonthlyVersion, PublicityEarningsImport, PublicityEarningsCurrent):
            model.__table__.create(self.engine)
        self.sessions=sessionmaker(self.engine,expire_on_commit=False)
        self.patches=[patch.object(api,'engine',self.engine),patch.object(api,'SessionLocal',self.sessions)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.engine.dispose()
    def run_fixture(self):
        grids={name:[[cell('old')]+[{}]*(spec['columns']-1)] for name,spec in api.SOURCES.items()}
        plan={'earnings':[(2,1,[[cell('new')]])],'master':[(1,1,[[cell('new')]])],'status':[[cell('Verified')]],'formats':[],'summary':{}}
        payload={'before':{n:{'grid':g} for n,g in grids.items()},'plan':plan,'end':api.today().strftime('%d/%m/%Y')}
        with self.sessions.begin() as session:session.add(McdoSyncRun(run_id='test',state='applying',payload=payload,result={}))
        return grids
    def state(self):
        with self.sessions() as session:return api.find_run(session,'test').state
    def test_sheet_import_preserves_the_last_verified_ireps_date(self):
        with self.sessions.begin() as session:
            session.add_all([
                McdoSyncRun(run_id='ireps',state='complete',updated_at=datetime(2026,11,24,tzinfo=timezone.utc),
                            payload={'end':'24/11/2026','plan':{'summary':{'new_invoices':2}}},result={}),
                McdoSyncRun(run_id='sheets',state='complete',updated_at=datetime(2026,11,25,tzinfo=timezone.utc),
                            payload={'mode':'sheets_to_oracle'},result={'monthly_report':{'period':'2026-10'}}),
            ])
        with patch.object(api,'read_ledger',return_value=([], None)), patch.object(api,'dashboard',return_value={}), \
                patch.object(api,'list_registry_contracts',return_value=[]):
            result = api.mcdo()['data']
        self.assertEqual(result['last_verified_check']['through'],'24/11/2026')
        self.assertEqual(result['last_verified_check']['new_invoices'],2)
        self.assertEqual(result['report_update']['period'],'2026-10')

    def test_manual_edit_aborts_both_writes(self):
        grids=self.run_fixture();fake=FakeSheets(grids);fake.grids['master'][0][0]=cell('manual edit')
        with patch.object(api,'Sheets',return_value=fake),patch.object(api,'import_sources') as importer:api.apply_worker('test')
        self.assertEqual(self.state(),'needs_review');self.assertEqual(fake.calls,[]);importer.assert_not_called()
    def test_partial_write_resumes_without_reappending(self):
        fake=FakeSheets(self.run_fixture())
        with patch.object(api,'Sheets',return_value=fake),patch.object(api,'import_sources',return_value={'verified':True}) as importer:
            api.apply_worker('test');self.assertEqual(self.state(),'needs_review');importer.assert_not_called()
            api.apply_worker('test');self.assertEqual(self.state(),'complete');importer.assert_called_once()
        self.assertEqual(entered(fake.grids['earnings'][1][0]),'new');self.assertEqual(len(fake.grids['earnings']),2)
        earnings=[p for name,p in fake.calls if name=='earnings']
        self.assertEqual(len(earnings[0]),1);self.assertEqual(len(earnings),1)
    def test_no_database_import_when_readback_fails(self):
        fake=FakeSheets(self.run_fixture());fake.fail_once=False
        original=fake.patches
        def discard(name,*args):
            original(name,*args)
            if name=='earnings':fake.grids[name][1][0]={}
        with patch.object(api,'Sheets',return_value=fake),patch.object(fake,'patches',side_effect=discard),patch.object(api,'import_sources') as importer:api.apply_worker('test')
        self.assertEqual(self.state(),'needs_review');importer.assert_not_called()
    def test_old_preview_is_refused(self):
        fake=FakeSheets(self.run_fixture())
        with self.sessions.begin() as session:
            r=api.find_run(session,'test');r.payload={**r.payload,'end':'01/01/2020'}
        with patch.object(api,'Sheets',return_value=fake):api.apply_worker('test')
        self.assertEqual(fake.calls,[]);self.assertEqual(self.state(),'needs_review')
    def test_incomplete_ireps_scan_is_refused(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):api.evidence_plan({}, {'completed_categories':['Advertising']})

    def test_bridge_separates_routine_scans_from_full_and_legacy_runs(self):
        from types import SimpleNamespace
        master = [{} for _ in range(37)]
        master[2], master[10], master[17] = cell('OLD-ACTIVE'), cell('Running'), cell(45000)
        before = {'earnings': {'grid': []}, 'master': {'grid': [[{}]*37, master]}}
        payload = {'before': before, 'start': '23/11/2026', 'end': '26/11/2026',
                   'contracts_since': '16/11/2026', 'scan_mode': 'incremental'}
        cfg = api.bridge_config(SimpleNamespace(run_id='routine',payload=payload))
        self.assertFalse(cfg['full_contract_reconciliation'])
        self.assertEqual(cfg['master_watch'][0]['dues'],[45000])
        self.assertEqual(cfg['contracts_since'],'16/11/2026')
        for mode in ('full', None):
            full = dict(payload)
            if mode: full['scan_mode'] = mode
            else: full.pop('scan_mode')
            self.assertTrue(api.bridge_config(SimpleNamespace(run_id='full',payload=full))['full_contract_reconciliation'])
        self.assertEqual(api.BeginRun().scan_mode,'incremental')

    def test_live_award_creates_master_row_before_first_receipt(self):
        last_receipt = [{} for _ in range(28)]
        last_receipt[2] = cell('23/11/2026')
        last_receipt[19] = cell('ES_EXISTING')
        earnings_heading = [{} for _ in range(28)]
        earnings_heading[19] = cell('Invoice')
        master_heading = [{} for _ in range(37)]
        master_heading[2], master_heading[16] = cell('Contract Number'), cell('Payment Due')
        master_existing = [{} for _ in range(37)]
        master_existing[2] = cell('SBC-Existing-26')
        first, last = '23/11/2026', '24/11/2026'
        payload = {'start':first,'end':last,'before':{
            'earnings':{'grid':[earnings_heading,last_receipt]},
            'master':{'grid':[master_heading,master_existing]}}}
        award = {'contract':'SBC-Foodtruck-SMVT-26','contract_date':'18/11/2026','firm':'Example',
                 'category':'Misc-Static-Services - Static General','asset':'MSS-SBC-SMVB-STGen-185',
                 'start':'15/12/2026','end':'14/12/2031','status':'LIVE'}
        contract_key = award['contract'].upper()
        evidence = {'start':first,'end':last,'completed_categories':api.CATEGORIES,'contracts':[award],
                    'contract_reconciliation':{'contracts':[award],'details':{
                        contract_key:{'agreement':'Verified agreement','schedule':[]}}}}
        terms = {'contract':award['contract'],'fee':3900000,'value':19500000,
                 'start':date(2026,12,15),'end':date(2031,12,14),'status':'LIVE','years':5,
                 'dates':[date(2026 + (11 + 3 * i) // 12, (11 + 3 * i) % 12 + 1, 15) for i in range(20)]}
        with patch.object(api,'contract_terms',return_value=terms):
            plan = api.evidence_plan(payload,evidence)
        self.assertEqual(plan['summary']['new_contracts'],1)
        self.assertEqual(plan['summary']['new_invoices'],0)
        row = next(rows[0] for n,c,rows in plan['master'] if n == 3 and c == 1)
        self.assertEqual((entered(row[2]),entered(row[3])),(award['contract'],'SMVB'))
        self.assertIn('First 19 of 20 open installments shown',entered(row[36]))
        # Targeted, officially read awards use the same verified agreement path
        # without claiming a complete lifecycle inventory.
        targeted = {k:v for k,v in evidence.items() if k != 'contract_reconciliation'}
        targeted['contract_updates'] = evidence['contract_reconciliation']
        with patch.object(api,'contract_terms',return_value=terms):
            incremental = api.evidence_plan(payload,targeted)
        self.assertEqual(incremental['master'],plan['master'])

        pending = [{} for _ in range(37)]
        pending[2] = cell(award['contract'])
        pending[36] = cell('IREPS award confirmed. Installment schedule pending verification.')
        payload['before']['master']['grid'].append(pending)
        with patch.object(api,'contract_terms',return_value=terms):
            plan = api.evidence_plan(payload,evidence)
        self.assertEqual(plan['summary']['new_contracts'],0)
        row = next(rows[0] for n,c,rows in plan['master'] if n == 3 and c == 1)
        self.assertIsInstance(entered(row[17]),int)
        self.assertIn('IREPS award confirmed.',entered(row[36]))
        self.assertNotIn('pending verification',entered(row[36]))
    def test_interrupted_sheets_import_resumes_in_database_only_mode(self):
        from fastapi import BackgroundTasks
        with self.sessions.begin() as session:
            session.add(McdoSyncRun(run_id='test',state='needs_review',payload={'mode':'sheets_to_oracle'},result={}))
        tasks=BackgroundTasks()
        api.apply('test',tasks,{})
        self.assertEqual(self.state(),'applying')
        self.assertEqual(tasks.tasks[0].args,('test',True))

    def test_sheets_import_schedules_worker_after_session_commit(self):
        from fastapi import BackgroundTasks
        tasks=BackgroundTasks()
        with patch.object(api,'SessionLocal',sessionmaker(self.engine,expire_on_commit=True)):
            response=api.sync_existing_sheets(tasks)
        self.assertEqual(len(tasks.tasks),1)
        run_id=tasks.tasks[0].args[0]
        self.assertEqual(tasks.tasks[0].args,(run_id,True))
        with self.sessions() as session:
            self.assertEqual(api.find_run(session,run_id).state,'applying')

    def test_play_one_stage_stops_before_master_and_resumes(self):
        from fastapi import BackgroundTasks
        fake=FakeSheets(self.run_fixture());fake.fail_once=False
        with self.sessions.begin() as session:api.find_run(session,'test').state='preview_ready'
        with patch.object(api,'Sheets',return_value=fake),patch.object(api,'import_sources',return_value={'verified':True}) as importer:
            api.apply('test',BackgroundTasks(),{'through_stage':3});api.apply_worker('test')
            self.assertEqual(self.state(),'paused');self.assertEqual([n for n,_ in fake.calls],['earnings']);importer.assert_not_called()
            api.apply('test',BackgroundTasks(),{'through_stage':4});api.apply_worker('test')
            self.assertEqual(self.state(),'paused');self.assertEqual([n for n,_ in fake.calls],['earnings','master']);importer.assert_not_called()
            api.apply('test',BackgroundTasks(),{'through_stage':5});api.apply_worker('test')
            self.assertEqual(self.state(),'complete');importer.assert_called_once()

    def test_pause_during_write_verifies_current_sheet_then_stops(self):
        fake=FakeSheets(self.run_fixture());fake.fail_once=False
        original=fake.patches
        def pause_after_write(name,*args):
            original(name,*args);api.pause_run('test')
        with patch.object(api,'Sheets',return_value=fake),patch.object(fake,'patches',side_effect=pause_after_write),patch.object(api,'import_sources') as importer:
            api.apply_worker('test');importer.assert_not_called()
        self.assertEqual(self.state(),'paused');self.assertEqual([n for n,_ in fake.calls],['earnings'])
        with self.sessions() as session:self.assertTrue(api.find_run(session,'test').result['earnings_verified'])

    def test_play_cannot_skip_dependencies(self):
        from fastapi import BackgroundTasks
        self.run_fixture()
        with self.sessions.begin() as session:api.find_run(session,'test').state='preview_ready'
        for stage in (4,5):
            with self.assertRaises(HTTPException) as err:api.apply('test',BackgroundTasks(),{'through_stage':stage})
            self.assertEqual(err.exception.status_code,409)

    def test_pause_while_reading_sources_stops_before_database_import(self):
        from fastapi import BackgroundTasks
        with self.sessions.begin() as session:
            session.add(McdoSyncRun(run_id='test',state='applying',payload={'mode':'sheets_to_oracle'},result={}))
        fake=FakeSheets({name:[] for name in api.SOURCES});original=fake.read
        def pause_during_read(*args):
            api.pause_run('test');return original(*args)
        with patch.object(api,'Sheets',return_value=fake),patch.object(fake,'read',side_effect=pause_during_read),patch.object(api,'import_sources') as importer:
            api.apply_worker('test',True);self.assertEqual(self.state(),'paused');importer.assert_not_called()
        with patch.object(api,'Sheets',return_value=fake),patch.object(api,'import_sources',return_value={'verified':True}) as importer:
            api.apply('test',BackgroundTasks(),{'through_stage':5});api.apply_worker('test',True)
            self.assertEqual(self.state(),'complete');importer.assert_called_once()

    def test_admin_access_is_closed_by_default(self):
        with patch.dict(os.environ,{'MCDO_ADMIN_TOKEN':''}):
            with self.assertRaises(HTTPException) as err:api.administrator(None)
            self.assertEqual(err.exception.status_code,503)
        with patch.dict(os.environ,{'MCDO_ADMIN_TOKEN':'x'*40}):
            with self.assertRaises(HTTPException):api.administrator('Bearer bad')
            api.administrator('Bearer '+'x'*40)
    def test_master_general_format_date_serials_are_preserved(self):
        row=[{} for _ in range(37)]
        row[5]={'effectiveValue':{'numberValue':46301}}
        row[17]={'effectiveValue':{'numberValue':46301}}
        raw=computed_workbook('master',{'grid':[row]})
        sheet=load_workbook(BytesIO(raw),data_only=True).active
        self.assertEqual(sheet.cell(1,6).value.date(),date(2026,10,6))
        self.assertEqual(sheet.cell(1,18).value.date(),date(2026,10,6))

    def test_operator_session_rejects_tampering_expiry_and_rotated_key(self):
        from mcdo.auth import issue_session
        with patch.dict(os.environ,{'MCDO_ADMIN_TOKEN':'x'*40}):
            token=issue_session()['session_token']
            api.administrator('Bearer '+token)
            with self.assertRaises(HTTPException):api.administrator('Bearer '+token[:-1]+'z')
            with patch('mcdo.auth.time.time',return_value=9999999999):
                with self.assertRaises(HTTPException):api.administrator('Bearer '+token)
        with patch.dict(os.environ,{'MCDO_ADMIN_TOKEN':'y'*40}):
            with self.assertRaises(HTTPException):api.administrator('Bearer '+token)

if __name__=='__main__':unittest.main()
