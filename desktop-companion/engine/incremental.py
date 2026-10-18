"""Target installment due dates, because IREPS does not filter collection dates."""
from datetime import timedelta
from core import actual, day, key, status_name, master_contract_key

def category_for(raw,categories):
    return next((c for c in categories if raw.startswith(c)),None)

def merge_ranges(ranges):
    result=[]
    for start,end in sorted(set(ranges)):
        if result and start <= result[-1][1]+timedelta(days=1):
            result[-1]=(result[-1][0],max(end,result[-1][1]))
        else:
            result.append((start,end))
    return result

def queries(master,statuses,failures,previous_failures,categories):
    """Cover active schedules, failed dues, and untracked active contracts.

    Untracked contracts are searched by exact identity, so a new contract does
    not depend on guessing its first payment date. A full reconciliation remains
    available for payments against old closed contracts with no known balance.
    """
    bycontract={master_contract_key(r):r for r in master[1:] if master_contract_key(r)}
    windows={c:[] for c in categories}
    extra=[]
    for k,s in statuses.items():
        category=category_for(s['category'],categories)
        if not category or status_name(s['status'])!='Running':
            continue
        row=bycontract.get(k)
        if row is None:
            extra.append((category,s['contract'],'01/01/1900','31/12/2099'))
            continue
        dates=[day(actual(c)) for c in row[17:36] if actual(c)!='']
        if dates:
            windows[category].append((min(dates),max(dates)))
    for failure in list(previous_failures)+list(failures):
        category=category_for(failure['category'],categories)
        if category:
            d=day(failure['due'])
            windows[category].append((d,d))
    result=[]
    for category in categories:
        result.extend((category,'',a.strftime('%d/%m/%Y'),b.strftime('%d/%m/%Y')) for a,b in merge_ranges(windows[category]))
    return result+sorted(set(extra))

def invoice_needed(invoice,contract,due,existing,known_due):
    if invoice not in existing:
        return True
    k=key(contract)
    # Retain recorded payments when the master still needs their installment
    # evidence. Otherwise do not download and parse the same PDF again.
    if k not in known_due:
        return True
    return known_due[k] is not None and known_due[k] <= day(due)
