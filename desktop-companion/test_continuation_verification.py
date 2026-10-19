import copy
import unittest
from dataclasses import asdict
from datetime import date
from test_continuation import ContinuationTests
from rp.rules import calculate
from rp.verifier import verify
from deskflow import Deskflow

class ContinuationVerificationTests(unittest.TestCase):
    def record(self):
        fixture=ContinuationTests();fixture.setUp()
        fixture.inputs['conditions_reviewed']=True
        return {'key':'L','revision':'r','lot':fixture.lot,'auctions':fixture.events,'contract':{},'inputs':fixture.inputs,'result':asdict(calculate(fixture.lot,fixture.events,{},fixture.inputs))}

    def test_exact_fractional_factor_and_baseline_pass_independent_checks(self):
        r=self.record()
        self.assertEqual(r['result']['multiplier'],'0.729')
        checks={c['code']:c['state'] for c in verify(r)['checks']}
        self.assertEqual(checks['calculation'],'pass')
        self.assertEqual(checks['pricing_basis'],'pass')

    def test_tampered_factor_and_scope_fail(self):
        for change in ('factor','scope'):
            r=self.record()
            if change=='factor':r['result']['multiplier']='0.73'
            else:r['lot']['description']='different asset'
            checks={c['code']:c['state'] for c in verify(r)['checks']}
            self.assertEqual(checks['pricing_basis'],'fail')

    def test_previous_parcel_rate_has_independent_amount_and_cycle_checks(self):
        r=self.record();r['inputs']['family']='Parcel'
        r['inputs']['continuation'].update(mode='parcel_previous',date='2026-09-07',base='8522.10',failed_dates=['2026-09-07','2026-09-23'])
        r['auctions']=[{'date':d,'outcome':'No Bids','source':'IREPS','catalogue':d} for d in ('2026-09-07','2026-09-23')]
        r['result']=asdict(calculate(r['lot'],r['auctions'],{},r['inputs']))
        checks={c['code']:c['state'] for c in verify(r)['checks']}
        self.assertEqual(r['result']['rp'],'7669.89');self.assertEqual(checks['pricing_basis'],'pass')
        r['inputs']['continuation']['failed_dates']=['2026-09-07','2026-09-24']
        self.assertEqual({c['code']:c['state'] for c in verify(r)['checks']}['pricing_basis'],'fail')

    def test_specific_saved_review_issue_is_preserved(self):
        d=object.__new__(Deskflow)
        self.assertEqual(d.result({},[],{},{'review_issue':'Confirm the cancelled contract reason.'})['missing'],'Confirm the cancelled contract reason.')

    def test_round_trip_aliases_do_not_create_false_unit_failures(self):
        r=self.record();r['lot']['rate_unit']='Per Round Trip ( Two Way )'
        r['inputs']['continuation']['rate_unit']='Per Round Trip Licensing Fee'
        r['auctions']=[{'date':'2026-09-01','outcome':'Sold','source':'IREPS','rate_unit':'Per Round Trip Licensing Fee','awardee':'A','bid_rate':'100'}]
        checks={c['code']:c['state'] for c in verify(r)['checks']}
        self.assertEqual(checks['bid_and_lar'],'pass')

if __name__=='__main__':unittest.main()
