"""Operational deadlines from the current Master register, using IST dates."""
from datetime import date, timedelta
from decimal import Decimal

def deadline_lists(contracts, asof):
    grace=[];overdue=[];expiry=[]
    for contract in contracts:
        if contract['source']['system']!='e_auction' or contract['status'] not in ('running','awarded'):
            continue
        common={'contract':contract['contract_number'],'contractor':(contract.get('contractor') or {}).get('legal_name'),
                'category':contract.get('category'),'source_row':contract['source'].get('row')}
        end=contract['period'].get('end')
        if end:
            remaining=(end-asof).days
            if 0<=remaining<=7:expiry.append({**common,'expiry_date':end.isoformat(),'days_remaining':remaining})
        schedules=sorted(contract.get('payment_schedule',[]),key=lambda s:s['installment_number'])
        # Master stores its current payment due first, followed by future dates.
        # Past dates alone do not prove payment failure or permit inferring settlement.
        if not schedules:continue
        current=schedules[0];due=current.get('due_date')
        if not due or due>asof:continue
        paid=sum((Decimal(str(p.get('amount_paid') or 0)) for p in contract.get('payments',[])
                  if p.get('schedule_id')==current['schedule_id']),Decimal(0))
        expected=current.get('expected_amount')
        if expected is not None and paid>=Decimal(str(expected)):continue
        ends=due+timedelta(days=2)
        item={**common,'due_date':due.isoformat(),'grace_ends':ends.isoformat(),
              'days_after_due':(asof-due).days,'amount_due':None if expected is None else str(max(Decimal(str(expected))-paid,Decimal(0)))}
        (grace if asof<=ends else overdue).append(item)
    return {'as_of':asof.isoformat(),'grace_days':2,
            'in_grace':sorted(grace,key=lambda r:(r['grace_ends'],r['contract'])),
            'past_grace':sorted(overdue,key=lambda r:(r['grace_ends'],r['contract'])),
            'expiring':sorted(expiry,key=lambda r:(r['days_remaining'],r['contract'])),
            'expiry_counts':{str(n):sum(r['days_remaining']<=n for r in expiry) for n in (3,5,7)}}
