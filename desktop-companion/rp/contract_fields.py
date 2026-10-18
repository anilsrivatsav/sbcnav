"""Map visible contract columns without inventing rates or award dates."""
import re

def contract_status(value):
    text=str(value or'').strip().casefold()
    if text in('live','running','active'):return'Running'
    if text in('completed','complete','expired'):return'Completed'
    if text in('foreclosed','foreclose'):return'Foreclosed'
    if text in('not commenced','not signed'):return str(value).strip().capitalize()
    if text in('cancelled','canceled','terminated'):return'Cancelled (reason unknown)'
    return'Unknown'

def candidate_fields(row):
    out={}
    for field,pattern in [('contract',r'contract.*(no|number)'),('awardee',r'licensee|licencee|contractor'),('lar',r'licen.*fee|\blar\b|bid rate'),('status',r'^status$'),('start',r'start|^from$'),('end',r'end|expiry|to date')]:
        value=next((v for k,v in row.items()if re.search(pattern,k,re.I)),None)
        if value:out[field]=contract_status(value)if field=='status'else value
    out['source']=row.get('source','')
    # Creation Date is not proof of contract award date. No mapping is made.
    return out
