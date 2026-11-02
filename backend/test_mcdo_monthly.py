import os
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
import io
import base64
import unittest
from copy import deepcopy
from datetime import date
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from mcdo.monthly import ASSETS, calculate, export_workbook, period_dates
from mcdo.auth import administrator
from models import McdoMonthlyPeriod, McdoMonthlyVersion
import mcdo_monthly_router as api


def row(number, month, amount, code='Z-611', year='2026-27'):
    y = int(year[:4])+(month < 4)
    return {'source_row': number, 'financial_year': year, 'month': month,
            'receipt_date': date(y,month,10), 'nfr_earnings': amount,
            'detailed_head': code, 'source_values': {'Invoice': f'ES{number}'}}


def configuration():
    return {'annual_target_crore': '28.9', 'target_source': 'FY target order',
            'earnings_complete': True, 'earnings_checked_through': '2026-10-31',
            'earnings_note': 'All April–October collections reconciled; other months zero.',
            'asset_position_date': '2026-11-02', 'asset_source': 'IREPS SBC dated asset reports 02/11/2026, October closing position',
            'assets_verified': True,
            'assets': {name: {'registered': 10, 'leased': 7, 'newly_created': 1} for name in ASSETS}}


SOURCE = {'import_id':'test-ledger','filename':'Main Sheet','warnings':[]}
ROWS = [row(2,4,'10000000'),row(3,10,'2500000','Z-617')]
NOW = date(2026,11,2)


class MonthlyCalculationTests(unittest.TestCase):
    def report(self, rows=None, config=None, period='2026-10'):
        return calculate(period, ROWS if rows is None else rows, SOURCE, configuration() if config is None else config, NOW)

    def test_full_precision_and_reconciliation(self):
        report=self.report()
        self.assertEqual(report['status'],'Ready to Complete')
        self.assertEqual(report['earnings']['previous_crore'],'1')
        self.assertEqual(report['earnings']['current_crore'],'0.25')
        self.assertEqual(report['earnings']['cumulative_crore'],'1.25')
        self.assertEqual(report['policies_crore']['Z-617'],'0.25')

    def test_missing_amount_and_unmapped_policy_block_completion(self):
        rows=deepcopy(ROWS);rows[0]['nfr_earnings']=None;rows[1]['detailed_head']='Z-999'
        report=self.report(rows)
        self.assertEqual(report['status'],'Needs Correction')
        self.assertTrue(any('missing' in i for i in report['issues']))
        with self.assertRaises(ValueError):export_workbook(report,1)

    def test_detailed_head_owns_reporting_policy(self):
        rows=deepcopy(ROWS);rows[0]['allocation_code']='00617000'
        report=self.report(rows)
        self.assertEqual(report['status'],'Ready to Complete')
        self.assertTrue(any('Detailed Head' in n for n in report['notes']))

    def test_duplicate_invoice_and_wrong_date_block(self):
        rows=deepcopy(ROWS);rows[1]['source_values']['Invoice']='ES2';rows[0]['receipt_date']=date(2025,4,10)
        issues=self.report(rows)['issues']
        self.assertTrue(any('duplicate' in i for i in issues))
        self.assertTrue(any('date' in i for i in self.report(rows)['notes']))

    def test_open_month_cannot_complete(self):
        self.assertIn('The selected month has not closed.',self.report(period='2026-11')['pending'])

    def test_ending_month_alone_is_not_completion(self):
        config=configuration();config['earnings_complete']=False
        self.assertEqual(self.report(config=config)['status'],'Data Pending')

    def test_missing_asset_categories_and_leased_overflow(self):
        config=configuration();config['assets'].pop('ATM');config['assets']['RDN']['leased']=11
        report=self.report(config=config)
        self.assertTrue(report['pending']);self.assertTrue(report['issues'])

    def test_weighted_total_idle_percentage_and_zero_denominator(self):
        config=configuration();config['assets']={n:{'registered':0,'leased':0,'newly_created':0} for n in ASSETS}
        config['assets']['RDN']={'registered':10,'leased':5,'newly_created':0}
        config['assets']['ATM']={'registered':90,'leased':90,'newly_created':0}
        report=self.report(config=config)
        self.assertEqual(report['asset_totals']['idle_percent'],'5')
        self.assertIsNone(report['assets']['OOH']['idle_percent'])

    def test_later_receipts_do_not_change_completed_month_fingerprint(self):
        self.assertEqual(self.report()['fingerprint'],self.report(ROWS+[row(4,11,'1234')])['fingerprint'])
        changed=deepcopy(ROWS);changed[0]['nfr_earnings']='10000001'
        self.assertNotEqual(self.report()['fingerprint'],self.report(changed)['fingerprint'])

    def test_april_reset_and_january_fiscal_year(self):
        self.assertEqual(period_dates('2027-01')[3],'2026-27')
        config=configuration();config['earnings_checked_through']='2026-04-30'
        report=self.report([row(2,4,'1')],config,'2026-04')
        self.assertEqual(report['earnings']['previous_crore'],'0')

    def test_export_preserves_format_without_other_division_figures(self):
        report=self.report()
        book=load_workbook(io.BytesIO(export_workbook(report,1)),data_only=True)
        self.assertEqual(book.sheetnames,['Immediate earning ','Policywise ','Idle Assets '])
        earning=book['Immediate earning '];policy=book['Policywise ']
        self.assertEqual(earning['F10'].value,policy['L8'].value)
        self.assertAlmostEqual(earning['E10'].value,28.9*7/12)
        self.assertIsNone(earning['H9'].value)
        self.assertIsNone(earning['F12'].value)
        self.assertEqual(earning['A12'].value,'SBC only')
        self.assertIn('October 2026',earning['F5'].value)
        self.assertEqual(book['Idle Assets ']['K19'].value,30)
        book.close()


class MonthlyApiTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        McdoMonthlyPeriod.__table__.create(self.engine)
        McdoMonthlyVersion.__table__.create(self.engine)
        self.sessions=sessionmaker(self.engine,expire_on_commit=False)
        self.rows=deepcopy(ROWS)
        self.patches=[patch.object(api,'SessionLocal',self.sessions),patch.object(api,'today',return_value=NOW),
                      patch.object(api,'read_ledger',side_effect=lambda session:(self.rows,SOURCE))]
        for p in self.patches:p.start()
        self.app=FastAPI();self.app.include_router(api.router)
        self.client=TestClient(self.app)
        self.app.dependency_overrides[administrator]=lambda:None

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.engine.dispose()

    def draft(self,config=None,revision=0):
        return self.client.post('/api/mcdo/monthly/2026-10/draft',json={'expected_revision':revision,'configuration':config or configuration()})

    def complete(self,fingerprint):
        return self.client.post('/api/mcdo/monthly/2026-10/complete',json={'fingerprint':fingerprint})

    def test_completion_is_idempotent_and_download_is_frozen(self):
        report=self.draft().json()['data']
        v1=self.complete(report['fingerprint']).json()['data']
        self.assertEqual(v1['id'],self.complete(report['fingerprint']).json()['data']['id'])
        path='/api/mcdo/monthly/2026-10/download/'+v1['id']
        original=self.client.get(path).content
        self.rows[0]['nfr_earnings']='10000001'
        self.assertEqual(original,self.client.get(path).content)
        self.assertEqual(self.complete(report['fingerprint']).status_code,409)
        report=self.client.get('/api/mcdo/monthly/2026-10').json()['data']
        v2=self.complete(report['fingerprint']).json()['data']
        self.assertEqual(v2['version'],2)
        self.assertEqual(len(self.client.get('/api/mcdo/monthly/2026-10').json()['data']['versions']),2)
        self.assertEqual(self.client.get('/api/mcdo/monthly/2026-09/download/'+v1['id']).status_code,404)

    def test_conflicting_draft_rejected(self):
        self.assertEqual(self.draft().status_code,200)
        self.assertEqual(self.draft().status_code,409)

    def test_mutations_require_authentication(self):
        self.app.dependency_overrides.clear()
        with patch.dict(os.environ,{'MCDO_ADMIN_TOKEN':'a'*40}):
            self.assertEqual(self.draft().status_code,401)

    def test_incomplete_and_invalid_months_rejected(self):
        config=configuration();config['assets_verified']=False
        report=self.draft(config).json()['data']
        self.assertEqual(self.complete(report['fingerprint']).status_code,422)
        self.assertEqual(self.client.get('/api/mcdo/monthly/2026-13').status_code,422)

    def test_source_and_inputs_must_be_revalidated(self):
        report=self.draft().json()['data']
        config=configuration();config['annual_target_crore']='30'
        self.assertEqual(self.draft(config,1).status_code,200)
        self.assertEqual(self.complete(report['fingerprint']).status_code,409)

    def test_supplied_workbook_download_is_byte_identical(self):
        content=export_workbook(calculate('2026-10',ROWS,SOURCE,configuration(),NOW),1)
        payload={'filename':'Supplied October.xlsx','workbook_base64':base64.b64encode(content).decode()}
        response=self.client.post('/api/mcdo/monthly/2026-10/reference',json=payload)
        self.assertEqual(response.status_code,200,response.text)
        version=response.json()['data']
        again=self.client.post('/api/mcdo/monthly/2026-10/reference',json=payload).json()['data']
        self.assertEqual(version['id'],again['id'])
        state=self.client.get('/api/mcdo/monthly/2026-10').json()['data']
        self.assertEqual(state['status'],'Ready to Download')
        self.assertEqual(state['origin'],'supplied_reference')
        self.rows[0]['nfr_earnings']='999999'
        self.assertEqual(self.client.get('/api/mcdo/monthly/2026-10').json()['data']['earnings']['previous_crore'],'1.0')
        downloaded=self.client.get('/api/mcdo/monthly/2026-10/download/'+version['id'])
        self.assertEqual(downloaded.content,content)


if __name__=='__main__':unittest.main()
