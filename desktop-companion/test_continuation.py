import copy
import unittest
from rp.rules import calculate, reviewed_continuation_matches

class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.lot = dict(lot='L', description='same asset', rate_unit='Annual Licensing Fee', start='2026-11-01', status='RP Pending')
        self.inputs = dict(family='Catering / MPS', identity_verified=True, benchmark_source='Finance source', continuation={
            **{k:self.lot[k] for k in ('lot','description','rate_unit')}, 'date':'2026-06-29',
            'source':'workbook row 812', 'policy':'HQ letter', 'scope_source':'catalogue detail',
            'base':'20995.2', 'mode':'successive', 'prior_failures':5})
        self.events=[dict(date=d,outcome=o,source='IREPS',catalogue=d) for d,o in [
            ('2026-06-29','No Bids'),('2026-07-29','Withdrawn'),('2026-09-08','No Bids'),('2026-09-30','No Bids')]]
    def test_repeat_is_stable_and_withdrawn_not_counted(self):
        for _ in range(2):
            r=calculate(self.lot,self.events,{},self.inputs)
            self.assertTrue(r.ready,r.missing);self.assertEqual(r.rp,'15305.50')
    def test_changed_scope_blocks(self):
        self.lot['description']='different scope'
        self.assertFalse(calculate(self.lot,self.events,{},self.inputs).ready)

    def test_refresh_preserves_review_only_for_exact_sourced_scope(self):
        self.inputs['conditions_reviewed']=True
        self.events=[{**e,**{k:self.lot[k] for k in ('lot','description','rate_unit')}} for e in self.events]
        self.assertTrue(reviewed_continuation_matches(self.lot,self.events,self.inputs))
        self.events[0]['description']='different compartment'
        self.assertFalse(reviewed_continuation_matches(self.lot,self.events,self.inputs))
    def test_new_award_blocks(self):
        self.events.append(dict(date='2026-10-01',outcome='Sold',source='IREPS',awardee='A',bid_rate=1000,rate_unit=self.lot['rate_unit']))
        self.assertFalse(calculate(self.lot,self.events,{},self.inputs).ready)
    def test_duplicate_failure_blocks(self):
        self.events.append(copy.deepcopy(self.events[0]))
        self.assertFalse(calculate(self.lot,self.events,{},self.inputs).ready)
    def test_parcel_four_failures_are_three_reductions(self):
        self.inputs['family']='Parcel';self.inputs['continuation'].update(mode='parcel_initial',base='9469')
        self.events[1]['outcome']='No Bids'
        self.assertEqual(calculate(self.lot,self.events,{},self.inputs).rp,'6628.30')

    def test_latest_parcel_rp_reduction_uses_previous_rate_once(self):
        self.inputs['family']='Parcel'
        self.inputs['continuation'].update(mode='parcel_previous',base='8522.10',date='2026-09-07',failed_dates=['2026-09-07','2026-09-23'])
        self.events=[dict(date=d,outcome='No Bids',source='IREPS',catalogue=d) for d in ('2026-09-07','2026-09-23')]
        for _ in range(2):
            r=calculate(self.lot,self.events,{},self.inputs)
            self.assertTrue(r.ready,r.missing);self.assertEqual(r.rp,'7669.89')
        self.events.append(dict(date='2026-10-01',outcome='No Bids',source='IREPS',catalogue='later'))
        self.assertFalse(calculate(self.lot,self.events,{},self.inputs).ready)

if __name__=='__main__':unittest.main()
