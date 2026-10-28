"""Password-gated browser view and authenticated desktop relay for Deskflow."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select

from database import SessionLocal
from mcdo.auth import administrator
from models import AuctionScheduleLink, DeskflowRelay, DeskflowWorkbookArchive
from mcdo.eauction import _category, live_schedule, save_schedule, list_holidays, save_holidays, delete_holiday
from deskflow_archive import decrypt_archive, encrypt_archive, update_archive

router = APIRouter(prefix='/api/deskflow', tags=['Deskflow'])
_attempt_lock = threading.Lock()
_attempts = []


def _secret():
    secret = os.getenv('MCDO_ADMIN_TOKEN', '')
    if len(secret) < 32:
        raise HTTPException(503, 'Deskflow authentication is not configured.')
    return secret.encode()


def _browser(authorization: str | None = Header(None)):
    token = (authorization or '').removeprefix('Bearer ')
    try:
        prefix, payload, signature = token.split('.')
        expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
        claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
        valid = prefix == 'deskflow' and hmac.compare_digest(signature, expected)
        valid = valid and claims.get('aud') == 'deskflow' and time.time() < claims.get('exp', 0) <= time.time() + 3600
    except (ValueError, TypeError, AttributeError, KeyError):
        valid = False
    if not valid:
        raise HTTPException(401, 'Unlock Deskflow again.')


def _row(session):
    row = session.execute(select(DeskflowRelay).where(DeskflowRelay.id == 1).with_for_update()).scalar_one_or_none()
    if row is None:
        row = DeskflowRelay(id=1, overview={}, software_update={}, command={})
        session.add(row)
        session.flush()
    return row


def _with_schedule_verification(lot, link):
    schedule = {'date': link.auction_date.isoformat(), 'status': link.status,
                'scheduleId': link.schedule_id, 'catalogueId': link.catalogue_id} if link else None
    verification = lot.get('verification')
    if not verification:
        return {**lot, 'auctionSchedule': schedule}
    checks = list(verification.get('checks', []))
    if not link:
        checks.append({'code': 'auction_schedule', 'state': 'warn', 'message': 'Link this lot to an auction schedule before final review.'})
    elif link.status != 'scheduled':
        checks.append({'code': 'auction_schedule', 'state': 'fail', 'message': f'Auction schedule is {link.status}; review the proposed value before use.'})
    elif lot.get('date', '')[:10] != schedule['date'] or _category(lot.get('category') or '') != _category(link.category or ''):
        checks.append({'code': 'auction_schedule', 'state': 'fail', 'message': 'Scheduled auction date or category does not match the collected IREPS lot.'})
    else:
        checks.append({'code': 'auction_schedule', 'state': 'pass', 'message': f"Scheduled auction {schedule['date']} matches the collected lot."})
    status = 'blocked' if any(c['state'] == 'fail' for c in checks) else 'needs_review' if any(c['state'] == 'warn' for c in checks) else 'verified'
    return {**lot, 'auctionSchedule': schedule, 'verification': {**verification, 'status': status, 'checks': checks}}


@router.post('/unlock')
def unlock(payload: dict = Body(...)):
    password = payload.get('password')
    if not isinstance(password, str) or len(password) > 256:
        raise HTTPException(400, 'Enter the Deskflow password.')
    now = time.monotonic()
    with _attempt_lock:
        _attempts[:] = [attempt for attempt in _attempts if now - attempt < 60]
        if len(_attempts) >= 30:
            raise HTTPException(429, 'Too many attempts. Try again in a minute.')
        _attempts.append(now)
    configured = os.getenv('DESKFLOW_PASSWORD', 'Antara')
    if not hmac.compare_digest(hashlib.sha256(password.encode()).digest(), hashlib.sha256(configured.encode()).digest()):
        raise HTTPException(401, 'Incorrect password.')
    expires = int(time.time()) + 3600
    claims = {'aud': 'deskflow', 'exp': expires, 'nonce': secrets.token_hex(16)}
    encoded = base64.urlsafe_b64encode(json.dumps(claims, separators=(',', ':')).encode()).decode().rstrip('=')
    signature = hmac.new(_secret(), encoded.encode(), hashlib.sha256).hexdigest()
    return {'token': f'deskflow.{encoded}.{signature}'}


@router.get('/overview', dependencies=[Depends(_browser)])
def overview():
    with SessionLocal() as session:
        row = session.get(DeskflowRelay, 1)
        data = row.overview if row else {}
        connected = bool(row and row.last_seen_at and (datetime.now(timezone.utc) - row.last_seen_at.replace(tzinfo=row.last_seen_at.tzinfo or timezone.utc)).total_seconds() < 30)
        links = session.scalars(select(AuctionScheduleLink)).all()
        by_lot = {}
        def updated(link):
            value = link.updated_at or datetime.min.replace(tzinfo=timezone.utc)
            return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc)
        for link in links:
            if link.lot_key and (link.lot_key not in by_lot or updated(link) > updated(by_lot[link.lot_key])):
                by_lot[link.lot_key] = link
        result = {'collected_at': None, 'categories': [], 'lots': [], 'progress': {'busy': False, 'phase': 'waiting', 'message': 'Waiting for the Windows desktop companion.'}} | data
        result['lots'] = [_with_schedule_verification(lot, by_lot.get(lot.get('key'))) for lot in result['lots']]
        return {**result, 'desktop_connected': connected}


@router.get('/eauction', dependencies=[Depends(_browser)])
def eauction_rows():
    return {'data': live_schedule()}


@router.post('/eauction', dependencies=[Depends(_browser)])
def eauction_save(payload: dict = Body(...)):
    return {'data': save_schedule(payload)}


@router.get('/holidays', dependencies=[Depends(_browser)])
def holidays_get():
    return {'data': list_holidays()}


@router.post('/holidays', dependencies=[Depends(_browser)])
def holidays_save(payload: dict = Body(...)):
    return {'data': save_holidays(payload)}


@router.delete('/holidays', dependencies=[Depends(_browser)])
def holidays_delete(day: str):
    return {'data': delete_holiday(day)}


@router.get('/software-update', dependencies=[Depends(_browser)])
def software_update():
    with SessionLocal() as session:
        row = session.get(DeskflowRelay, 1)
        return row.software_update if row and row.software_update else {'phase': 'waiting', 'message': 'Waiting for the Windows desktop companion.'}


@router.get('/workbook-history', dependencies=[Depends(_browser)])
def workbook_history(book: str = '', q: str = Query('', max_length=120), page: int = Query(1, ge=1), limit: int = Query(30, ge=1, le=100), view: str = 'records'):
    if book not in ('', 'parcels', 'catering', 'others') or view not in ('records', 'rows'):
        raise HTTPException(400, 'Invalid workbook history filter.')
    with SessionLocal() as session:
        row = session.get(DeskflowWorkbookArchive, 1)
        if row is None:
            return {'available': False, 'books': [], 'items': [], 'total': 0, 'page': page, 'limit': limit}
        try:
            archive = decrypt_archive(row.ciphertext)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
    needle = q.strip().lower()
    books = [{'id': item['id'], 'portfolio': item['portfolio'], 'file': item['file'], 'rows': item['rowCount'], 'cells': item['cellCount']} for item in archive['workbooks']]
    if view == 'records':
        candidates = (item for item in archive['auctionRecords'] if not book or item['bookId'] == book)
        items = [item for item in candidates if not needle or needle in item['search']]
    else:
        items = []
        for workbook in archive['workbooks']:
            if book and workbook['id'] != book:
                continue
            for sheet in workbook['sheets']:
                for source_row in sheet['rows']:
                    if not needle or needle in source_row['s']:
                        items.append({'bookId': workbook['id'], 'file': workbook['file'], 'sheet': sheet['name'], 'row': source_row})
    offset = (page - 1) * limit
    return {
        'available': True, 'books': books, 'items': items[offset:offset + limit],
        'total': len(items), 'page': page, 'limit': limit, 'view': view,
        'generatedAt': archive['generatedAt'], 'sourceManifest': archive['sourceManifest'],
    }


@router.post('/{action}', dependencies=[Depends(_browser)])
def command(action: str, payload: dict = Body(...)):
    simple=('collect','history','software-update','sync-workbooks','save-reviewed','cancel')
    review=('link-asset','save-review','review-proposal')
    if action not in simple+review or (action in simple and payload != {}):
        raise HTTPException(400, 'Invalid Deskflow command.')
    if action in review:
        allowed={'key','revision'}|({'previous_lot','source','confirmed'} if action=='link-asset' else {'inputs','contract','auctions'} if action=='save-review' else {'proposal_revision'})
        if set(payload)-allowed or not all(isinstance(payload.get(name),str) and 0<len(payload[name])<=512 for name in ('key','revision')) or len(json.dumps(payload))>50_000:
            raise HTTPException(400,'Invalid review payload.')
    with SessionLocal.begin() as session:
        row = _row(session)
        if not row.last_seen_at or (datetime.now(timezone.utc) - row.last_seen_at.replace(tzinfo=row.last_seen_at.tzinfo or timezone.utc)).total_seconds() >= 30:
            raise HTTPException(503, 'Open the SBCNAV desktop companion on the Windows PC to run this command.')
        if row.command_id:
            raise HTTPException(409, 'A desktop command is already pending.')
        row.command_id = str(uuid4())
        row.command = {'action': action, **({'payload':payload} if payload else {})}
        return {'queued': True}


@router.post('/agent/sync', dependencies=[Depends(administrator)])
def agent_sync(payload: dict = Body(...)):
    overview = payload.get('overview')
    update = payload.get('software_update')
    if not isinstance(overview, dict) or not isinstance(update, dict):
        raise HTTPException(400, 'Invalid desktop state.')
    with SessionLocal.begin() as session:
        row = _row(session)
        row.overview = overview
        row.software_update = update
        row.last_seen_at = datetime.now(timezone.utc)
        if payload.get('ack_command_id') == row.command_id and row.command_id:
            row.command_id = None
            row.command = {}
        return {'command_id': row.command_id, **row.command} if row.command_id else {'command_id': None}


@router.post('/agent/workbook-archive', dependencies=[Depends(administrator)])
async def agent_workbook_archive(request: Request):
    if request.headers.get('content-type', '').split(';')[0] != 'application/zip':
        raise HTTPException(415, 'Upload a workbook ZIP bundle.')
    try:
        declared_size = int(request.headers.get('content-length', '0') or 0)
    except ValueError as exc:
        raise HTTPException(400, 'Invalid workbook bundle length.') from exc
    if declared_size > 8_000_000:
        raise HTTPException(413, 'Workbook bundle exceeds the 8 MB limit.')
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 8_000_000:
            raise HTTPException(413, 'Workbook bundle exceeds the 8 MB limit.')
        chunks.append(chunk)
    bundle = b''.join(chunks)
    if not bundle or len(bundle) > 8_000_000:
        raise HTTPException(413, 'Workbook bundle is empty or too large.')
    # Parsing Excel and encrypting the archive must not block the async worker's
    # heartbeat or the companion relay while an upload is being processed.
    return await run_in_threadpool(_save_workbook_archive, bundle)


def _save_workbook_archive(bundle: bytes):
    with SessionLocal.begin() as session:
        row = session.execute(select(DeskflowWorkbookArchive).where(DeskflowWorkbookArchive.id == 1).with_for_update()).scalar_one_or_none()
        if row is None:
            raise HTTPException(503, 'Import the initial workbook archive first.')
        try:
            archive, changed = update_archive(decrypt_archive(row.ciphertext), bundle)
            if changed:
                row.ciphertext = encrypt_archive(archive)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(400, str(exc)) from exc
    return {'changed': changed, 'generatedAt': archive['generatedAt'],
            'totalRows': archive['totalRows'], 'auctionRecordCount': archive['auctionRecordCount']}
