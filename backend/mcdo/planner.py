"""Create precise, repeatable patches from exported sheets and IREPS evidence."""
import re
from copy import deepcopy
from datetime import date
from .core import actual, entered, cell, literal, key, day, serial, earning_row, status_name, managed_note, unpaid_dates, master_contract_key

def main_plan(earnings, master, payments, terms, statuses, failures, asof):
    if actual(earnings[0][19]) != 'Invoice' and 'invoice' not in str(actual(earnings[0][19])).lower():
        # Some maintained sheets use multi-row headings. Match invoice evidence in data instead.
        if not any(re.fullmatch(r'ES\w+', str(actual(r[19]))) for r in earnings):
            raise RuntimeError('Earnings invoice column T cannot be confirmed.')
    if str(actual(master[0][2])).strip() != 'Contract Number':
        raise RuntimeError('Master contract header changed.')
    if str(actual(master[0][16])).strip() != 'Payment Due':
        raise RuntimeError('Master payment columns changed.')
    existing = {str(actual(r[19])).strip() for r in earnings if actual(r[19])}
    used = [i for i,r in enumerate(earnings) if actual(r[19])]
    last = max(used)
    fresh = [p for p in payments if p['invoice'] not in existing]
    newrows, epatches, mpatches, formats = [], [], [], []
    previous = earnings[last]
    last_date = day(actual(previous[2]))
    for p in fresh:
        if day(p['paid']) < last_date:
            raise RuntimeError(f"Unrecorded backdated invoice {p['invoice']} needs review before appending; no rows have been written.")
        n = last + 2 + len(newrows)
        row = earning_row(p,n,previous)
        if n-1 < len(earnings) and any(entered(c) for c in earnings[n-1]):
            raise RuntimeError('Earnings append area contains existing content.')
        newrows.append(row['values'])
        previous = row['values']
    if newrows:
        epatches.append((last+2,1,newrows))
        formats.append(('earnings', f'A{last+1}:AB{last+1}', f'A{last+2}:AB{last+1+len(newrows)}'))
    bycontract = {}
    for i,r in enumerate(master[1:],2):
        k = master_contract_key(r)
        if k:
            if k in bycontract:
                raise RuntimeError('Duplicate contract in master: '+str(entered(r[2])))
            bycontract[k] = i
    edge = max(bycontract.values())
    newcontracts = [k for k in terms if k not in bycontract]
    for i,k in enumerate(newcontracts):
        n = edge+1+i
        if n-1 < len(master) and any(entered(c) for c in master[n-1]):
            raise RuntimeError(f'New contract needs a blank row at {n}. Insert blank rows below the last contract and rerun; no data was written.')
        bycontract[k] = n
    paid = {}
    for p in payments:
        paid.setdefault(key(p['contract']),set()).add(day(p['due']))
    for k,t in terms.items():
        n = bycontract[k]
        row = deepcopy(master[n-1]) if n-1 < len(master) else [{} for _ in range(37)]
        new = k in newcontracts
        if new:
            p = next(p for p in payments if key(p['contract']) == k)
            s = statuses[k]
            nums = re.search(r'^SBC-(\d+)-',p['contract'])
            station = nums[1] if nums else next((v for v in ('SMVB','BWT','YPR','DPJ','YNK','KGI','HSRA','SBC') if v in s['asset'].split('-')[2:]),'')
            policy = 'Parking' if s['category'].startswith('Parking') else 'PMBJK' if s['category'].startswith('PMBJK') else 'ATM' if s['category'].startswith('ATM') else 'OOH' if 'Out of Home' in s['category'] else 'MA' if s['category'].startswith('Advertising') else 'MISC'
            for j,v in {1:s['firm'],2:p['contract'],3:station,4:policy,5:serial(s['contract_date']),6:s['category'],7:t['fee'],8:t['value'],10:status_name(t['status']),11:f'=H{n}/4',12:serial(t['start']),13:serial(t['end']),14:t['years'],15:'=TODAY()',16:f'=IF(R{n}="","",P{n}-R{n})'}.items():
                row[j] = cell(v) if j in (11,15,16) else literal(v)
            dates = unpaid_dates(t,paid.get(k,set()))
        else:
            current = actual(master[n-1][17])
            if current == '':
                # An empty due date can mean all installments were already paid.
                dates = []
            else:
                current = day(current)
                if current not in t['dates']:
                    raise RuntimeError(f"Existing due date for {t['contract']} disagrees with IREPS. Review before updating.")
                dates = [d for d in unpaid_dates(t,paid.get(k,set())) if d >= current]
        if len(dates) > 19:
            raise RuntimeError('Payment schedule exceeds the available master columns R:AJ.')
        for j in range(17,36):
            row[j] = cell(serial(dates[j-17])) if j-17 < len(dates) else {}
        if not dates:
            row[16] = cell(f'=IF(R{n}="","",P{n}-R{n})')
        row[36] = literal(managed_note(entered(row[36]), f"Paid installments verified {asof}; next due {dates[0].strftime('%d-%m-%Y') if dates else 'none (final installment paid)'}."))
        mpatches.append((n,1,[row]))
        if new:
            formats.append(('master', f'A{edge}:AK{edge}', f'A{n}:AK{n}'))
    issue_bycontract = {}
    for fail in failures:
        issue_bycontract.setdefault(key(fail['contract']),[]).append(f"Unpaid {fail['amount']} due {fail['due']} (beyond grace period)")
    def status_message(k):
        s = statuses.get(k)
        if not s:
            return None
        state = status_name(s['status'])
        issue = '; '.join(issue_bycontract.get(k,[]))
        return f"Checked {asof}: contract {state}" + ('; '+issue if issue else '; no beyond-grace payment failure listed')
    # Apply contract states only from explicit IREPS status, never from absence in a scan.
    for k,n in bycontract.items():
        msg = status_message(k)
        if msg is None:
            continue
        existing_patch = next((p for p in mpatches if p[0] == n),None)
        if existing_patch:
            existing_patch[2][0][10] = cell(status_name(statuses[k]['status']))
            existing_patch[2][0][36] = literal(managed_note(entered(existing_patch[2][0][36]),msg))
        else:
            if entered(master[n-1][10]) != status_name(statuses[k]['status']):
                mpatches.append((n,11,[[cell(status_name(statuses[k]['status']))]]))
            mpatches.append((n,37,[[literal(managed_note(entered(master[n-1][36]),msg))]]))
    remarks = []
    for i,r in enumerate(earnings[1:],2):
        msg = status_message(key(actual(r[4])))
        if msg:
            remarks.append((i,28,[[literal(managed_note(entered(r[27]),msg))]]))
    for i,r in enumerate(newrows,last+2):
        msg = status_message(key(entered(r[4])))
        if msg:
            r[27] = literal(managed_note(entered(r[27]),msg))
    epatches.extend(remarks)
    report = [['Checked on','Contract','Category','Contractor','Contract status','Failure status','Amount due','Pay by date','CP start','CP end']]
    for k,s in sorted(statuses.items()):
        failed = [f for f in failures if key(f['contract']) == k]
        for f in failed or [None]:
            report.append([asof,s['contract'],s['category'],s['firm'],status_name(s['status']),f['status'] if f else 'No beyond-grace failure listed',f['amount'] if f else '',f['due'] if f else '',s['start'],s['end']])
    if any(key(f['contract']) not in statuses for f in failures):
        raise RuntimeError('A failed-payment contract was missing from the contract scan. Expand contract_scan_from in config and rerun.')
    return dict(earnings=epatches, master=mpatches, formats=formats, status=[[literal(v) for v in r] for r in report],
                summary=dict(new_invoices=len(fresh),new_contracts=len(newcontracts),failed_payments=len(failures),not_running=sum(status_name(s['status'])!='Running' for s in statuses.values()),
                earnings_amount=round(sum(p['fee'] for p in fresh),2)))

def compact(patches):
    """Combine adjacent single-cell changes into a small number of native pastes."""
    output = []
    for r,c,rows in sorted(patches,key=lambda p:(p[1],p[0])):
        if output and output[-1][1] == c and output[-1][0]+len(output[-1][2]) == r and len(output[-1][2][0]) == len(rows[0]):
            output[-1][2].extend(rows)
        else:
            output.append((r,c,list(rows)))
    return output
