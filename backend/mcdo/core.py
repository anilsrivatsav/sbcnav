"""Deterministic invoice and sheet rules. No authentication or network calls."""
import re
from datetime import datetime, date
from decimal import Decimal
from io import BytesIO
from pypdf import PdfReader

def key(value):
    return re.sub(r"\s+", "", str(value or "")).upper()

def day(value):
    if isinstance(value, (float, int)):
        from datetime import timedelta
        return date(1899, 12, 30) + timedelta(days=value)
    value = str(value).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognized date: {value}")

def serial(value):
    return (day(value) - date(1899, 12, 30)).days

def cell(value):
    if value is None or value == "":
        return {}
    if isinstance(value, str) and value.startswith("="):
        return {"userEnteredValue": {"formulaValue": value}}
    return {"userEnteredValue": {"numberValue": value} if isinstance(value, (float, int)) else {"stringValue": str(value)}}

def literal(value):
    return {'userEnteredValue':{'stringValue':value}} if isinstance(value,str) and value!='' else cell(value)

def entered(c):
    v = c.get("userEnteredValue", {})
    return v.get("formulaValue", v.get("numberValue", v.get("stringValue", "")))

def actual(c):
    v = c.get("effectiveValue", c.get("userEnteredValue", {}))
    return v.get("numberValue", v.get("stringValue", c.get("formattedValue", "")))

def master_contract_key(row):
    value=actual(row[2])
    if value=='':return None
    # Scratch arithmetic below the table also uses column C. A numeric
    # value needs contractor text or contract state to identify a contract.
    firm=actual(row[1]);state=actual(row[10])
    if not isinstance(value,str) and not (isinstance(firm,str) and firm.strip()) and not state:
        return None
    return key(value)

def relevant(category):
    s = key(category)
    if s.startswith("PARKING"):
        return "RADIOTAXI" in s
    return any(s.startswith(x) for x in ("ADVERTISING", "MISC-STATIC", "MISC-MOBILE", "ATM", "PMBJK", "HYBRIDNFR"))

def invoice(data, record):
    text = "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(data)).pages)
    def between(a, b):
        # Match full field labels: 'Invoice Number' also occurs inside
        # 'Old Invoice Number', which must not supply the current identity.
        first = re.search(r'(?m)^' + re.escape(a) + r'[ \t]*$', text)
        last = re.search(r'(?m)^' + re.escape(b) + r'[ \t]*$', text[first.end():]) if first else None
        if not first or not last:
            raise ValueError(f"Invoice {record['invoice']}: missing {a}")
        return text[first.end():first.end()+last.start()].strip()
    nums = re.findall(r"\d+\.\d{2}", between("Collected Value (Rs.)", "Rate (%)"))
    if len(nums) < 3:
        raise ValueError("Unsupported invoice amount layout")
    supply, fee, collected = map(Decimal, nums[:3])
    taxes = {}
    for kind in ("CGST", "SGST", "IGST"):
        m = re.search(r"\n" + kind + r"\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+\.\d{2})", text)
        if m:
            taxes[kind] = Decimal(m[3])
    invno = between("Invoice Number", "Invoice Issue Date").replace("\n", "").strip()
    contract = re.sub(r"\s+", "", between("Contract No", "Contract Date"))
    if invno != record['invoice'] or key(contract) != key(record['contract']):
        raise ValueError("Invoice identity does not match payment row")
    if abs(collected - Decimal(str(record['total']))) > Decimal("0.01"):
        raise ValueError("Invoice amount does not match payment row")
    if abs(fee + sum(taxes.values()) - supply) > Decimal("1.01"):
        raise ValueError("Invoice GST reconciliation failed")
    if abs(collected - supply) > Decimal("1.01"):
        raise ValueError("Partial collection requires manual review")
    if between("Payment Type", "Lot No") != "Licence Fee" or between("RCM Applicable", "Invoice and Tax Charged Details") != "No":
        raise ValueError("Non-standard payment type or reverse-charge invoice requires manual review")
    person = re.split(r"GST No -\s*\n[A-Z0-9]+\s*\n", text, 1)[1].split("Name of Firm", 1)[0].strip()
    code = re.sub(r"\s+", "", between("Accounts Allocation\nCode", "State Code of Supplier"))
    if not re.fullmatch(r"\d{8}", code):
        raise ValueError("Unrecognized allocation code")
    return {**record, 'contract': contract, 'fee': float(fee), 'gst_amount': float(sum(taxes.values())),
            'taxes': {k: float(v) for k, v in taxes.items()}, 'code': code,
            'paid': between("Invoice Issue Date", "Accounts Allocation"),
            'transaction': between("Bank Transaction ID", "Payment Type"),
            'firm': re.sub(r"\s+", " ", between("Name of Firm", "Address of Firm").lstrip("-").strip()),
            'address': between("Address of Firm", "Telephone No-").lstrip("-").strip(),
            'gst': between("GST No -", "Contract No").split("GST No -")[-1].strip(), 'person': person,
            'service': between("Service Date", "Lot Desc")}

def financial_year(d):
    y = d.year if d.month >= 4 else d.year - 1
    return f"{y}-{str(y+1)[-2:]}"

def earning_row(p, n, previous):
    d = day(p['paid'])
    fy = financial_year(d)
    if str(actual(previous[0])) != fy:
        raise ValueError("A new financial year needs its opening balance and annual target configured in the sheet first.")
    cat = key(p['category'])
    group = "Parking" if cat.startswith('PARKING') else "PMBJK" if cat.startswith('PMBJK') else "ATM" if cat.startswith('ATM') else "Advertising" if cat.startswith('ADVERTISING') else "Misc"
    policy = "Parking" if group == 'Parking' else 'NINFRIS/eauction'
    vals = [fy, d.strftime('%B'), serial(d), 'NFR', p['contract'], policy, group, 'E', p['firm'], p['fee'], None, None,
            f'=J{n}+K{n}', f'=M{n}+L{n}', f'=O{n-1}+N{n}', f'=P{n-1}-N{n}',
            '=' + '+'.join(format(v,'.2f').rstrip('0').rstrip('.') for v in p['taxes'].values()) if p['taxes'] else 0,
            f'=N{n}+Q{n}', p['transaction'], p['invoice'], p['address'], p['gst'], p['person'], None,
            'Z-'+p['code'][-5:-2], None, int(p['code']), None]
    row = [cell(v) for v in vals]
    for j in (4,8,18,19,20,21,22):
        row[j]=literal(vals[j])
    row[19]['note'] = 'IREPS invoice source: ' + p['url']
    if abs(p['fee'] + p['gst_amount'] - float(p['total'])) > 0.001:
        row[17]['note'] = f"Calculated fee plus GST; IREPS collected amount was rounded to {p['total']}."
    return {'values': row}

def contract_terms(text, schedule, contract, status):
    def grab(pattern):
        m = re.search(pattern, text)
        if not m:
            raise ValueError(f"Unsupported contract layout: {contract}")
        return m[1].strip()
    if key(grab(r'Contract No\.\s+([^\t\n]+)')) != key(contract):
        raise ValueError("Wrong contract agreement returned")
    fee = float(grab(r'Rate \(Rs\.\)\s+(\d+(?:\.\d+)?)'))
    value = float(grab(r'Contract Value\s+Rs\.\s*([\d.]+)'))
    start = day(grab(r'Contract Start Date\s+([\d/]+)'))
    end = day(grab(r'Contract End Date\s+([\d/]+)'))
    years = int(grab(r'Contract Duration\s+(\d+) Years'))
    if not schedule or any(len(s) < 10 or s[3] != 'Quarterly' for s in schedule):
        raise ValueError(f"Only verified quarterly schedules are currently supported: {contract}")
    dates = [day(s[4]) for s in schedule]
    if dates != sorted(set(dates)):
        raise ValueError("Payment schedule is not strictly increasing")
    waived=[day(s[4]) for s in schedule if len(s)>10 and s[10].startswith('Waived')]
    return dict(contract=contract, fee=fee, value=value, start=start, end=end, years=years, dates=dates, status=status,waived_dates=waived)

def status_name(raw):
    s = key(raw)
    if s in ('LIVE', 'PUBLISHED', 'RUNNING'):
        return 'Running'
    if s in ('CANCELLED', 'CANCELED'):
        return 'Cancelled'
    if s in ('COMPLETED', 'EXPIRED', 'CLOSED'):
        return 'Completed'
    return str(raw).strip()

def managed_note(old, message):
    tag = '[IREPS Updater]'
    old = str(old or '').split(tag, 1)[0].rstrip()
    return (old + '\n\n' if old else '') + tag + ' ' + message

def unpaid_dates(terms, paid_due):
    # Dates are removed only when a specific paid invoice proves the installment.
    settled=set(paid_due)|{day(d) for d in terms.get('paid_dates',[])}|{day(d) for d in terms.get('waived_dates',[])}
    result = [d for d in terms['dates'] if d not in settled]
    return result

def latest_recorded_date(earnings):
    dates = []
    annotated = []
    for number, row in enumerate(earnings, 1):
        if len(row) < 20 or not str(actual(row[19])).strip():
            continue
        # A real invoice identifies a recorded earning; headers and totals do not.
        if not str(actual(row[19])).strip().upper().startswith('ES'):
            continue
        try:
            if '?' in str(actual(row[2])):
                raise ValueError('Annotated date')
            dates.append(day(actual(row[2])))
        except (ValueError, TypeError):
            marker = re.fullmatch(r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})\s*\?', str(actual(row[2])).strip())
            if marker:
                try:
                    annotated.append((number, day(marker[1])))
                    continue
                except ValueError:
                    pass
            raise RuntimeError(f'The recorded invoice at earnings row {number} has an invalid date. Correct that row before updating.')
    if not dates:
        raise RuntimeError('No dated invoice found in the earnings Main Sheet. Check the configured sheet and date column C.')
    latest = max(dates)
    for number, uncertain in annotated:
        if uncertain >= latest:
            raise RuntimeError(f'The date at earnings row {number} is marked uncertain and could be the latest date. Confirm that date before updating.')
    return latest
