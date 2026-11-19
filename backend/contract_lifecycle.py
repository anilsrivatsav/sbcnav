"""Evidence-led lifecycle and receipt reconciliation. Never infer closure from receipts."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlalchemy import select
from models import (ContractRegistryContract as Contract, ContractRegistryContractor as Contractor,
                    ContractRegistryEvidence as Evidence, ContractRegistryEvent as Event,
                    ContractRegistryIssue as Issue, ContractRegistryPayment as Payment,
                    ContractRegistryPaymentSchedule as Schedule, PublicityEarning,
                    PublicityEarningsCurrent)

CATEGORIES = ['Advertising', 'Misc-Static-Services', 'Misc-Mobile-Services',
              'ATM/DBU/Banking e-Lobby', 'PMBJK', 'Parking', 'Hybrid NFR',
              'Catering', 'MPS', 'Pay and Use', 'Parcel']
CLOSED = {'cancelled', 'terminated', 'foreclosed', 'completed', 'expired'}


def identity(value):
    # Whitespace/case only: punctuation is part of the official contract identity.
    return re.sub(r'\s+', '', str(value or '')).upper()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(str(value or '').strip()[:10], fmt).date()
        except ValueError:
            pass
    return None


def money(value):
    try:
        number = Decimal(str(value).replace(',', '').strip())
        return number.quantize(Decimal('.01')) if number.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def normalized_status(value):
    text = re.sub(r'[^a-z]+', ' ', str(value or '').lower()).strip()
    if text in {'live', 'running', 'active', 'operational'}:
        return 'running'
    if re.fullmatch(r'(?:contract )?foreclos(?:ed|ure)', text):
        return 'foreclosed'
    if re.fullmatch(r'(?:contract )?terminat(?:ed|ion)', text):
        return 'terminated'
    if re.fullmatch(r'(?:contract )?cancel(?:led|ed|lation)', text):
        return 'cancelled'
    if text in {'completed', 'closed', 'contract completed'}:
        return 'completed'
    if text in {'expired', 'suspended', 'awarded'}:
        return text
    return 'unknown'


def visible_status(contract, asof=None):
    asof = asof or datetime.now(ZoneInfo('Asia/Kolkata')).date()
    status = contract.status or 'unknown'
    if status != 'running':
        return status
    if not contract.source_present:
        return 'verification_required'
    if contract.period_start and contract.period_start > asof:
        return 'not_started'
    if contract.period_end and contract.period_end < asof:
        return 'expiry_review'
    if not contract.ireps_checked_at or not contract.period_start or not contract.period_end:
        return 'verification_required'
    return 'running'


def labelled_fields(detail):
    """Only actual label/value cells, never generic SCC text or link captions."""
    result = {}
    for row in detail.get('fields', []):
        if len(row) != 2 or any('\n' in str(x) for x in row):
            continue
        label = re.sub(r'\s+', ' ', str(row[0]).strip(' :\t\n')).lower()
        if len(label) <= 70 and len(str(row[1])) <= 2000:
            result[label] = str(row[1]).strip()
    return result


def lifecycle(record, detail, previous=None):
    status = normalized_status(record.get('status'))
    fields = labelled_fields(detail or {})
    explicit = next((normalized_status(fields[k]) for k in
                     ('contract status', 'current contract status', 'status')
                     if k in fields and normalized_status(fields[k]) != 'unknown'), None)
    issues = []
    if explicit and explicit != status:
        issues.append('list_detail_status_conflict')
        status = 'status_conflict'
    effective = reason = reference = None
    for state, prefix in (('terminated', 'termination'), ('foreclosed', 'foreclosure'), ('cancelled', 'cancellation')):
        event_date = day(fields.get(prefix + ' effective date') or fields.get(prefix + ' date')
                         or fields.get('date of ' + prefix))
        # A labelled closure date is evidence; a clause mentioning the word is not.
        if event_date:
            if status == 'running':
                issues.append('closure_reinstatement_requires_review')
                status = 'status_conflict'
            elif status in {state, 'cancelled', 'unknown'}:
                status = state
                effective = event_date
                reason = fields.get(prefix + ' reason') or fields.get('reason for ' + prefix)
                reference = fields.get(prefix + ' order number') or fields.get(prefix + ' order no')
    if previous in CLOSED and status == 'running':
        status = 'status_conflict'
        issues.append('reinstatement_order_required')
    if status in {'cancelled', 'terminated', 'foreclosed'}:
        if not effective:
            issues.append('closure_effective_date_missing')
        if not reason:
            issues.append('closure_reason_missing')
        if not reference:
            issues.append('closure_order_reference_missing')
    if not detail:
        issues.append('contract_details_not_verified')
    return dict(status=status, effective=effective, reason=reason, reference=reference, issues=issues)


def record_issue(session, contract_id, code, detail, now):
    issue_id = digest([contract_id, code, detail])
    row = session.get(Issue, issue_id)
    if not row:
        row = Issue(issue_id=issue_id, contract_id=contract_id, code=code, detail=detail,
                    opened_at=now, last_seen_at=now)
        session.add(row)
    else:
        row.last_seen_at = now
        row.resolved_at = None
    return issue_id


def canonicalize(session):
    contracts = session.scalars(select(Contract)).all()
    official = {}
    for row in contracts:
        if row.source_system == 'e_auction':
            official.setdefault(identity(row.contract_number), []).append(row)
    linked = conflicts = 0
    for row in contracts:
        if row.source_system == 'e_auction':
            continue
        # Full exact reference only; station/licensee similarity cannot merge contracts.
        matches = official.get(identity(row.contract_name), [])
        if len(matches) == 1:
            target = matches[0]
            if row.contract_id == target.contract_id:
                continue
            if row.status != target.status:
                conflicts += 1
            row.canonical_contract_id = target.contract_id
            row.reconciliation_state = 'alias'
            linked += 1
        elif len(matches) > 1:
            record_issue(session, row.contract_id, 'ambiguous_canonical_reference',
                         {'reference': row.contract_name}, datetime.now(timezone.utc))
    return dict(aliases=linked, conflicting_aliases=conflicts)


def validate_evidence(evidence):
    if evidence.get('collection_complete') is not True:
        raise ValueError('Contract scan is incomplete; saved checkpoints cannot be applied.')
    if set(evidence.get('completed_categories', [])) != set(CATEGORIES):
        raise ValueError('All eleven contract categories must be checked.')
    if set(evidence.get('completed_payment_categories', [])) != set(CATEGORIES):
        raise ValueError('Full receipt inventory is incomplete.')
    asof = day(evidence.get('asof'))
    if not asof or asof > datetime.now(ZoneInfo('Asia/Kolkata')).date():
        raise ValueError('Invalid contract verification date.')
    records = {}
    for record in evidence.get('contracts', []):
        key = identity(record.get('contract'))
        if not key or key in records:
            raise ValueError('Missing or duplicate official contract identity.')
        records[key] = record
    if not records:
        raise ValueError('Empty official inventory cannot replace the contract register.')
    invoices = {}
    for receipt in evidence.get('payments', []):
        invoice = identity(receipt.get('invoice'))
        if not re.fullmatch(r'ES\w+', invoice) or not day(receipt.get('paid')) or money(receipt.get('total')) is None:
            raise ValueError('Invalid official receipt identity, date or amount.')
        if invoice in invoices and invoices[invoice] != receipt:
            raise ValueError('Conflicting invoice observations.')
        invoices[invoice] = receipt
    return asof, records, invoices


def reconcile(session, evidence):
    """Caller owns the transaction. Evidence, aliases and receipts commit together."""
    asof, records, invoices = validate_evidence(evidence)
    now = datetime.combine(asof, datetime.min.time(), tzinfo=timezone.utc)
    observed = datetime.now(timezone.utc)
    existing = {identity(c.contract_number): c for c in session.scalars(
        select(Contract).where(Contract.source_system == 'e_auction')).all()}
    counts = Counter()
    for key, record in records.items():
        contract = existing.get(key)
        if not contract:
            name = str(record.get('firm') or 'Unknown contractor').strip()
            normalized = re.sub(r'[^a-z0-9]+', ' ', name.lower()).strip()
            contractor = session.scalar(select(Contractor).where(Contractor.normalized_name == normalized))
            if not contractor:
                contractor = Contractor(legal_name=name, normalized_name=normalized)
                session.add(contractor); session.flush()
            contract = Contract(source_system='e_auction', contract_number=record['contract'],
                                contract_name=record.get('asset') or record['contract'],
                                contractor_id=contractor.contractor_id, contract_family='other', status='unknown',
                                award_method='e_auction', category=record.get('category'))
            session.add(contract); session.flush()
            existing[key] = contract
            counts['created'] += 1
        if contract.ireps_checked_at and contract.ireps_checked_at.date() > asof:
            raise ValueError('Older evidence cannot overwrite a newer official observation.')
        detail = evidence.get('details', {}).get(key)
        result = lifecycle(record, detail, contract.status if contract.ireps_checked_at else None)
        content = {'inventory': record, 'detail': detail}
        evidence_id = digest([contract.contract_id, asof, content])
        if not session.get(Evidence, evidence_id):
            session.add(Evidence(evidence_id=evidence_id, contract_id=contract.contract_id,
                                 source='IREPS authenticated contract view', checked_at=now,
                                 sha256=digest(content), content=content))
            session.flush()
        previous = contract.status
        contract.source_present = True
        contract.ireps_status = record.get('status')
        contract.ireps_checked_at = now
        contract.period_start = day(record.get('start'))
        contract.period_end = day(record.get('end'))
        contract.contract_date = day(record.get('contract_date'))
        contract.status = result['status']
        contract.status_effective_date = result['effective']
        contract.status_reason = result['reason']
        contract.reconciliation_issues = result['issues']
        contract.reconciliation_state = 'review_required' if result['issues'] else 'verified'
        contract.lifecycle_verified_at = now if not result['issues'] else None
        if contract.period_end and contract.period_end < asof and contract.status == 'running':
            contract.reconciliation_issues = [*contract.reconciliation_issues, 'extension_or_expiry_order_required']
            contract.reconciliation_state = 'review_required'
        for code in contract.reconciliation_issues:
            record_issue(session, contract.contract_id, code, {'asof': str(asof), 'evidence_id': evidence_id}, observed)
        last = session.scalar(select(Event).where(Event.contract_id == contract.contract_id)
                              .order_by(Event.observed_at.desc(), Event.event_id).limit(1))
        if (not last or last.event_type != contract.status or last.effective_date != result['effective']
                or last.reason != result['reason'] or (result['reference'] and last.source_reference != result['reference'])):
            event_id = digest([contract.contract_id, previous, contract.status, result['effective'], evidence_id])
            if not session.get(Event, event_id):
                session.add(Event(event_id=event_id, contract_id=contract.contract_id,
                                  event_type=contract.status, effective_date=result['effective'],
                                  observed_at=observed, reason=result['reason'],
                                  source_reference=result['reference'] or 'ireps:' + evidence_id, evidence_id=evidence_id))
        if detail:
            try:
                with session.begin_nested():
                    apply_schedule(session, contract, detail, evidence_id)
            except ValueError:
                code = 'official_schedule_needs_review'
                contract.reconciliation_issues = [*contract.reconciliation_issues, code]
                contract.reconciliation_state = 'review_required'
                record_issue(session, contract.contract_id, code, {'evidence_id': evidence_id}, observed)
        counts[visible_status(contract, asof)] += 1
    for key, contract in existing.items():
        if key not in records:
            contract.source_present = False
            contract.reconciliation_state = 'review_required'
            contract.reconciliation_issues = ['absent_from_latest_inventory']
            record_issue(session, contract.contract_id, 'absent_from_latest_inventory', {'asof': str(asof)}, observed)
            counts['absent_from_inventory'] += 1
    session.flush()
    counts.update(canonicalize(session))
    session.flush()
    counts.update(link_receipts(session, invoices, existing, observed))
    session.flush()
    return {'asof': str(asof), 'inventory': len(records), 'rdn': sum(k.startswith('SBC-RDN-') for k in records),
            'counts': dict(counts), 'detail_exceptions': evidence.get('errors', []),
            'warnings': evidence.get('warnings', []), 'evidence_hash': digest(evidence)}


def apply_schedule(session, contract, detail, evidence_id):
    rows = detail.get('schedule', [])
    if not rows:
        return
    existing = {s.installment_number: s for s in session.scalars(
        select(Schedule).where(Schedule.contract_id == contract.contract_id)).all()}
    seen = set()
    for cells in rows:
        if len(cells) != 12 or not str(cells[0]).strip().isdigit():
            raise ValueError('Unsupported official schedule layout; no contract changes applied.')
        number = int(cells[0])
        if number in seen or not day(cells[4]):
            raise ValueError('Duplicate installment or missing official due date.')
        seen.add(number)
        schedule = existing.get(number)
        if not schedule:
            schedule = Schedule(contract_id=contract.contract_id, installment_number=number)
            session.add(schedule)
        schedule.is_current = True
        schedule.due_date = day(cells[4])
        schedule.period_label = f'{cells[2]} / {cells[3]}'
        schedule.charge_type, schedule.frequency = str(cells[2]), str(cells[3])
        schedule.period_start, schedule.period_end = day(cells[8]), day(cells[9])
        # Displayed '-' is unknown, not zero and not annual/4 guessed into every row.
        schedule.expected_amount = money(cells[6])
        # Embedded adjustment notes belong to the retained evidence snapshot.
        schedule.status = (str(cells[10]).partition('\n')[0].strip() or 'unknown')[:32]
        schedule.source_reference = 'ireps:' + evidence_id
    for number, schedule in existing.items():
        if number not in seen:
            schedule.is_current = False


def link_receipts(session, invoices, contracts, now, *, official_schedules_only=False):
    counts = Counter()
    ledger = {}
    imports = [r.import_id for r in session.scalars(select(PublicityEarningsCurrent)).all() if r.import_id]
    if imports:
        for row in session.scalars(select(PublicityEarning).where(PublicityEarning.import_id.in_(imports))).all():
            values = {str(k).strip().lower(): v for k, v in (row.source_values or {}).items()}
            inv = identity(values.get('invoice'))
            if inv:
                ledger.setdefault(inv, []).append((row, values))
    for inv, receipt in invoices.items():
        contract = contracts.get(identity(receipt['contract']))
        if not contract:
            record_issue(session, None, 'receipt_contract_missing', {'invoice': inv, 'contract': receipt['contract']}, now)
            counts['unmatched_receipts'] += 1
            continue
        candidates = ledger.get(inv, [])
        verified = []
        for row, values in candidates:
            if (identity(values.get('policy')) == identity(receipt['contract'])
                    and row.receipt_date == day(receipt['paid'])
                    and money(row.total_with_gst) == money(receipt['total'])):
                verified.append(row)
        # Keep the official receipt even when absent from the MCDO ledger (scope may differ).
        status = 'official_receipt'
        if len(candidates) > 1:
            status = 'duplicate_ledger_invoice'
        elif candidates and len(verified) != 1:
            status = 'ledger_mismatch'
        elif len(verified) == 1:
            status = 'ledger_matched'
        if status in {'duplicate_ledger_invoice', 'ledger_mismatch'}:
            record_issue(session, contract.contract_id, status, {'invoice': inv}, now)
            counts['receipt_exceptions'] += 1
        payment = session.scalar(select(Payment).where(Payment.receipt_key == 'ireps:' + inv))
        if not payment:
            payment = Payment(contract_id=contract.contract_id, receipt_key='ireps:' + inv,
                              invoice_number=inv, payment_reference=inv)
            session.add(payment)
        elif (payment.contract_id != contract.contract_id or money(payment.gross_amount) != money(receipt['total'])
              or payment.payment_date != day(receipt['paid'])):
            record_issue(session, contract.contract_id, 'changed_official_receipt', {'invoice': inv}, now)
            counts['receipt_exceptions'] += 1
            continue
        payment.payment_date = day(receipt['paid'])
        payment.due_date = day(receipt.get('due'))
        payment.gross_amount = money(receipt['total'])
        payment.verification_status = status
        payment.payment_status = 'collected' if payment.gross_amount > 0 else 'reversed_or_zero'
        if len(verified) == 1 and len(candidates) == 1:
            row = verified[0]
            payment.amount_paid = money(row.licence_fee)
            payment.gst_amount = money(row.gst)
            payment.penalty_amount = money(row.penalty)
            payment.source_reference = f'publicity_earnings:{row.import_id}:{row.source_row}'
        else:
            payment.source_reference = 'IREPS payment inventory:' + inv
        schedule_query = select(Schedule).where(Schedule.contract_id == contract.contract_id,
                    Schedule.due_date == payment.due_date, Schedule.is_current.is_(True))
        if official_schedules_only:
            schedule_query = schedule_query.where(Schedule.source_reference.startswith('ireps:'))
        matches = session.scalars(schedule_query).all() if payment.due_date else []
        if len(matches) == 1:
            payment.schedule_id = matches[0].schedule_id
        else:
            payment.schedule_id = None
            record_issue(session, contract.contract_id, 'receipt_installment_unallocated', {'invoice': inv}, now)
            counts['unallocated_receipts'] += 1
        counts['linked_receipts'] += 1
        if identity(contract.contract_number).startswith('SBC-RDN-'):
            counts['rdn_linked_receipts'] += 1
    return counts
