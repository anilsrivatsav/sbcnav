import unittest
from web_incremental import payment_queries, watched_contracts


class IncrementalTests(unittest.TestCase):
    def config(self):
        return {'categories': ['Advertising'], 'master_watch': [
            {'contract':'OLD', 'status':'Running', 'pending':False, 'dues':['01/04/2024','01/07/2024']},
            {'contract':'SETTLED', 'status':'Completed', 'pending':False, 'dues':[]},
            {'contract':'ACTIVE-PAID', 'status':'Running', 'pending':False, 'dues':[]},
            {'contract':'CLOSED-DUE', 'status':'Completed', 'pending':False, 'dues':['01/01/2023']}]}

    def test_old_unpaid_installments_and_closed_balances_are_not_lost(self):
        cfg = self.config()
        statuses = {r['contract']: {'contract':r['contract'], 'category':'Advertising'} for r in cfg['master_watch']}
        queries = payment_queries(cfg, statuses, [])
        self.assertEqual(queries, [('Advertising','','01/01/2023','01/01/2023'),
                                   ('Advertising','','01/04/2024','01/07/2024')])
        self.assertNotIn('SETTLED', watched_contracts(cfg, []))
        self.assertIn('ACTIVE-PAID', watched_contracts(cfg, []))
        self.assertIn('CLOSED-DUE', watched_contracts(cfg, []))

    def test_new_awards_and_missing_master_schedules_use_exact_identity(self):
        cfg = self.config()
        cfg['master_watch'].append({'contract':'PENDING','status':'Running','pending':True,'dues':[]})
        statuses = {k:{'contract':k,'category':'Advertising'} for k in ['NEW','PENDING']}
        self.assertEqual(payment_queries(cfg,statuses,[]),[
            ('Advertising','NEW','01/01/1900','31/12/2099'),
            ('Advertising','PENDING','01/01/1900','31/12/2099')])

    def test_overdue_failure_reopens_a_closed_contract_for_exact_check(self):
        failure = {'contract':'SETTLED','category':'Advertising','due':'01/01/2021'}
        self.assertIn('SETTLED',watched_contracts(self.config(),[failure]))
        self.assertEqual(payment_queries(self.config(),{},[failure]),[
            ('Advertising','','01/01/2021','01/01/2021')])
