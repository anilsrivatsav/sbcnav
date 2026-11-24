"""Read the official contract and receipt inventories in the existing IREPS session."""
import re
from core import day, relevant

CONTRACT_START = '01/01/2020'

CATEGORIES = ['Advertising', 'Misc-Static-Services', 'Misc-Mobile-Services',
              'ATM/DBU/Banking e-Lobby', 'PMBJK', 'Parking', 'Hybrid NFR',
              'Catering', 'MPS', 'Pay and Use', 'Parcel']


def collect_inventory(reader, controller, asof, checkpoint, *, master_contracts=None):
    evidence = {'asof': asof, 'contracts': [], 'details': {}, 'payments': [], 'errors': [],
                'contract_conflicts': {},
                'warnings': [], 'completed_categories': [], 'completed_payment_categories': []}

    reader.navigate('Contracts')
    seen = {}
    for category in CATEGORIES:
        controller.log('Contract inventory: ' + category)
        for row in reader.read_category_rows('Contracts', category, 'contracts',
                                             start=CONTRACT_START, end=asof):
            c = row['cells']
            if len(c) != 9 or not c[0].strip():
                continue
            item = dict(contract=c[0], contract_date=c[1], firm=c[2], category=c[3],
                        asset=c[4], start=c[5], end=c[6], status=c[7])
            key = re.sub(r'\s+', '', c[0]).upper()
            if key in evidence['contract_conflicts']:
                if item not in evidence['contract_conflicts'][key]:
                    evidence['contract_conflicts'][key].append(item)
                continue
            if key in seen and seen[key] != item:
                evidence['contract_conflicts'][key] = [seen.pop(key), item]
                controller.log('Conflicting IREPS rows held for review: ' + c[0])
                continue
            seen[key] = item
        evidence['contracts'] = list(seen.values())
        evidence['completed_categories'].append(category)
        checkpoint(evidence)
    def needs_master_agreement(item):
        key, record = item
        if master_contracts is None or key in master_contracts or record['status'].upper() != 'LIVE':
            return False
        category = record['category']
        if not (relevant(category) or category.startswith('Pay and Use - Lounges / Waiting / Retiring / Cloak Rooms')):
            return False
        try:
            return day(record['end']) >= day(asof)
        except ValueError:
            return False

    ordered = sorted(seen.items(), key=lambda item: (not needs_master_agreement(item),
                     not item[0].startswith('SBC-RDN-'), item[0]))
    for index, (key, record) in enumerate(ordered, 1):
        controller.checkpoint()
        controller.log(f'Official contract details {index}/{len(ordered)}: {record["contract"]}')
        try:
            reader.navigate('Contracts')
            reader.search('---All---', start=CONTRACT_START, end=asof, contract=record['contract'])
            rows = reader.all_rows('contracts', filtered=True)
            if len(rows) != 1 or re.sub(r'\s+', '', rows[0]['cells'][0]).upper() != key:
                raise RuntimeError('Exact contract lookup did not return one matching contract.')
            with reader.page.expect_navigation(wait_until='domcontentloaded'):
                reader.click_read_control(reader.page.get_by_role('link', name='Contract', exact=True), 'Contract')
            fields = reader.page.locator('table tr').evaluate_all(
                '''(rows)=>rows.map(r=>[...r.cells].map(c=>c.innerText.trim()))
                    .filter(r=>r.length===2 && r[0].length<=70 &&
                        /status|termination|foreclosure|cancellation|contract no/i.test(r[0]))''')
            schedule = []
            button = reader.page.get_by_role('button', name='Payment Schedule', exact=True)
            if button.count() == 1:
                with reader.page.expect_popup() as popup:
                    reader.click_read_control(button, 'Payment Schedule')
                schedule_page = popup.value
                try:
                    schedule_page.locator('body').wait_for()
                    heading = schedule_page.locator('body').inner_text()
                    if record['contract'].upper() not in heading.upper():
                        raise RuntimeError('Payment schedule belongs to a different contract.')
                    schedule = schedule_page.locator('tr[id^="row-"]').evaluate_all(
                        '(rows)=>rows.map(r=>[...r.cells].map(c=>c.innerText.trim()))')
                finally:
                    schedule_page.close()
            evidence['details'][key] = {'contract': record['contract'],
                'fields': fields, 'schedule': schedule, 'checked_through': asof}
            if needs_master_agreement((key, record)):
                evidence['details'][key]['agreement'] = reader.page.locator('body').inner_text()
        except Exception as exc:
            reader.check()  # Abort on a lost session or a closed window.
            evidence['errors'].append({'contract': record['contract'], 'stage': 'details',
                                       'error_type': type(exc).__name__})
            controller.log('Detail verification needs review: ' + record['contract'])
        checkpoint(evidence)
    reader.navigate('Payments')
    invoices = {}
    for category in CATEGORIES:
        controller.log('Full contract receipt inventory: ' + category)
        for row in reader.read_category_rows('Payments', category, 'paid',
                                             kind='Previous Payments Made', start='01/01/1900', end='31/12/2099'):
            c = row['cells']
            if len(c) != 9 or not re.fullmatch(r'ES\w+', c[8]):
                continue
            item = dict(invoice=c[8], paid=c[0], total=c[1], contract=c[2],
                        contract_date=c[3], category=c[4], asset=c[5], firm=c[6], due=c[7])
            if item['invoice'] in invoices and invoices[item['invoice']] != item:
                raise RuntimeError('Conflicting official invoice observations.')
            invoices[item['invoice']] = item
        evidence['payments'] = list(invoices.values())
        evidence['completed_payment_categories'].append(category)
        checkpoint(evidence)
    evidence['warnings'] = [*reader.warnings, *(
        f'Conflicting IREPS inventory rows held for review: {key}'
        for key in sorted(evidence['contract_conflicts'])
    )]
    evidence['collection_complete'] = True
    checkpoint(evidence)
    return evidence
