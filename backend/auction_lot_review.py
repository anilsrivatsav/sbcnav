"""Record schedule and review changes from the authenticated Deskflow relay."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from itertools import islice

from sqlalchemy import select, tuple_

from models import AuctionLotHistory

IST = timezone(timedelta(hours=5, minutes=30))


def _at(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        try:
            stamp = datetime.strptime(value, '%d-%m-%y %H:%M:%S')
        except ValueError:
            return None
    return stamp.replace(tzinfo=stamp.tzinfo or IST).astimezone(IST)


def _identity(entry):
    catalogue = str(entry.get('catalogue') or '').strip().upper()
    lot = str(entry.get('lot') or '').strip().upper()
    if catalogue.startswith(('SBC-', 'SBC_', 'SBC ')) and lot and len(catalogue) <= 160 and len(lot) <= 200:
        return catalogue, lot
    return None


def _unique(entries):
    rows, conflicts = {}, set()
    for entry in entries:
        if not isinstance(entry, dict) or not (key := _identity(entry)):
            continue
        if key in rows and rows[key] != entry:
            conflicts.add(key)
        rows[key] = entry
    return {key: entry for key, entry in rows.items() if key not in conflicts}


def _schedule(entry):
    start = _at(entry.get('start') or entry.get('date'))
    if not start:
        return None
    result = {field: entry.get(field) or '' for field in ('catalogue', 'lot', 'category')}
    return {**result, 'start': start.isoformat(), 'description': entry.get('description') or entry.get('details') or ''}


def _fields(entry, names):
    return {key: entry[key] for key in names.split() if key in entry}


def _review(entry, collected_at):
    proposal = _fields(entry.get('proposal') or {}, 'revision status policy_version value formula base factor justification')
    verification = entry.get('verification') or {}
    sources = entry.get('review') or {}
    inputs = sources.get('inputs') or {}
    return {
        'collected_at': collected_at.isoformat(),
        'key': entry.get('key'),
        'rate_unit': entry.get('rate_unit') or '',
        'rule': entry.get('rule') or '',
        'proposal': proposal,
        'checks': verification.get('checks') or [],
        'basis': _fields(inputs, 'benchmark_source continuation'),
        'contract': _fields(sources.get('contract') or {}, 'id contract_id lar rate_unit status source award_date start end closed'),
        'precedents': entry.get('history') or [],
        'workbook': _fields(entry.get('workbook_source') or {}, 'workbook path sheet row value notes'),
    }


def _rows(session, keys):
    # Keep the composite lookup comfortably below the bind limit on SQLite and PostgreSQL.
    remaining = iter(keys)
    while batch := list(islice(remaining, 250)):
        yield from session.scalars(select(AuctionLotHistory).where(
            tuple_(AuctionLotHistory.catalogue, AuctionLotHistory.lot).in_(batch)
        ))


def record_lots(session, published, overview, observed_at):
    """Called while the relay row is locked, in the same transaction as the sync."""
    published = published or {}
    published_at = _at(published.get('checked_at'))
    work = _unique(overview.get('lots') or [])
    collected_at = _at(overview.get('collected_at'))
    schedule = _unique(published.get('lots') or [])
    by_key = {(row.catalogue, row.lot): row for row in _rows(session, schedule.keys() | work.keys())}
    for key in schedule.keys() | work.keys():
        row = by_key.get(key)
        entry = work.get(key)
        announced = schedule.get(key)
        work_schedule = _schedule(entry) if entry and collected_at else None
        published_schedule = _schedule(announced) if announced and published_at else None
        # A newer complete schedule remains authoritative if an older collection is replayed.
        incoming = published_schedule or work_schedule
        if incoming is None:
            continue
        source_at = published_at if published_schedule else collected_at
        stored_at = _at(row.schedule.get('observed_at')) if row else None
        previous = row.schedule if row else {}
        if not row and published_at and not published_schedule and collected_at <= published_at:
            continue
        if stored_at is not None and source_at < stored_at:
            incoming = _fields(previous, 'catalogue lot category start description')
            source_at = stored_at
        previous_core = _fields(previous, 'catalogue lot category start description')
        next_schedule = {**incoming, 'observed_at': source_at.isoformat()}
        events = list(row.events) if row else []
        review = row.review if row else {}
        if incoming != previous_core:
            events.append({'at': source_at.isoformat(), 'kind': 'schedule', 'data': incoming})
            if previous:
                review = {}
        prior_collection = _at(review.get('collected_at'))
        if (work_schedule and work_schedule == incoming
                and (prior_collection is None or collected_at >= prior_collection)):
            candidate = _review(entry, collected_at)
            if _review_content(candidate) != _review_content(review):
                events.append({'at': observed_at.isoformat(), 'kind': 'review', 'data': candidate})
            review = candidate
        if row is None:
            row = AuctionLotHistory(catalogue=key[0], lot=key[1])
            session.add(row)
        row.auction_at = _at(incoming['start'])
        row.schedule = next_schedule
        row.review = review
        row.events = events


def _review_content(review):
    return {key: value for key, value in review.items() if key != 'collected_at'}


def review_status(review, auction_at, as_of, archived=False):
    if not review:
        return 'pending', ['Collect this lot in Deskflow to load its RP evidence.']
    checks = review.get('checks') or []
    relevant = [check for check in checks if check.get('code') != 'local_workbook']
    reasons = [check.get('message') or 'A Deskflow evidence check needs review.'
               for check in relevant if check.get('state') != 'pass']
    if not archived and _at(review['collected_at']).date() < min(as_of.date(), auction_at.date()):
        reasons.insert(0, 'Refresh the scheduled lot and RP evidence in Deskflow for today.')
    required = {'scheduled_collection', 'history_coverage', 'calculation', 'pricing_basis', 'justification'}
    if required - {check.get('code') for check in relevant}:
        reasons.append('Run the Deskflow evidence and calculation checks.')
    proposal = review.get('proposal') or {}
    try:
        amount = Decimal(str(proposal.get('value')))
        valid_amount = amount.is_finite() and amount > 0
    except InvalidOperation:
        valid_amount = False
    remark = proposal.get('justification')
    if not valid_amount or not isinstance(remark, str) or not 0 < len(remark.strip()) <= 300 or not review.get('rate_unit'):
        reasons.append('A positive RP, rate unit and a justification of 1–300 characters are required.')
    if reasons:
        return 'pending', reasons
    status = proposal.get('status')
    if status in ('ready_for_review', 'reviewed', 'saved'):
        if status == 'saved' and not any(c.get('code') == 'local_workbook' and c.get('state') == 'pass' for c in checks):
            return 'reviewed', ['Verify the workbook still matches the saved proposal.']
        return ('ready' if status == 'ready_for_review' else status), []
    return 'pending', ['Resolve outstanding evidence in Deskflow.']


def list_lots(session, published, month, now):
    published = published or {}
    now = now.astimezone(IST)
    current = _unique(published.get('lots') or [])
    if month:
        start = date.fromisoformat(month + '-01')
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        records = session.scalars(select(AuctionLotHistory).where(
            AuctionLotHistory.auction_at >= datetime.combine(start, datetime.min.time(), IST),
            AuctionLotHistory.auction_at < datetime.combine(end, datetime.min.time(), IST)
        )).all()
    else:
        records = list(_rows(session, current))
    lots = []
    for row in records:
        auction_at = _at(row.schedule['start'])
        published_lot = current.get((row.catalogue, row.lot))
        published_schedule = _schedule(published_lot) if published_lot else None
        is_current = bool(published_schedule and _at(published_schedule['start']) == auction_at and auction_at > now)
        if not month and not is_current:
            continue
        status, reasons = review_status(row.review, auction_at, now, archived=auction_at <= now)
        if auction_at > now and not is_current:
            status = 'pending'
            reasons = ['This lot is absent from the latest published IREPS schedule.', *reasons]
        lots.append({
            **row.schedule, 'current': is_current, 'status': status, 'reasons': reasons,
            'review': row.review, 'events': row.events,
        })
    lots.sort(key=lambda item: (item['start'], item['catalogue'], item['lot']))
    return {'checked_at': published.get('checked_at'), 'lots': lots}
