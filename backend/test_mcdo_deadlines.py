import unittest
from datetime import date,timedelta
from mcdo.deadlines import deadline_lists

class DeadlineTests(unittest.TestCase):
    asof=date(2026,10,7)
    def contract(self,name,end,due,status='running',paid=0):
        return {'contract_number':name,'category':'Advertising','contractor':{'legal_name':'Firm'},'status':status,
                'source':{'system':'e_auction','row':2},'period':{'end':self.asof+timedelta(days=end)},
                'payment_schedule':[{'schedule_id':1,'installment_number':2,'due_date':self.asof+timedelta(days=due),'expected_amount':100}],
                'payments':[{'schedule_id':1,'amount_paid':paid}]}
    def test_grace_includes_due_day_and_second_day_but_not_third(self):
        result=deadline_lists([self.contract(str(d),20,d) for d in (-3,-2,-1,0,1)],self.asof)
        self.assertEqual({r['contract'] for r in result['in_grace']},{'-2','-1','0'})
        self.assertEqual([r['contract'] for r in result['past_grace']],['-3'])
    def test_expiry_windows_are_cumulative_and_exclude_inactive_and_expired(self):
        contracts=[self.contract(str(d),d,2) for d in (-1,0,3,4,5,6,7,8)]
        contracts.append(self.contract('cancelled',1,0,'cancelled'))
        self.assertEqual(deadline_lists(contracts,self.asof)['expiry_counts'],{'3':2,'5':4,'7':6})
    def test_paid_schedule_is_excluded_and_partial_balance_is_preserved(self):
        result=deadline_lists([self.contract('paid',10,-1,paid=100),self.contract('partial',10,-1,paid=40)],self.asof)
        self.assertEqual([(r['contract'],r['amount_due']) for r in result['in_grace']],[('partial','60')])
    def test_missing_due_is_not_invented(self):
        contract=self.contract('missing',3,0);contract['payment_schedule']=[]
        result=deadline_lists([contract],self.asof)
        self.assertEqual(result['in_grace'],[]);self.assertEqual(result['expiry_counts']['3'],1)
