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

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from sqlalchemy import select

from database import SessionLocal
from mcdo.auth import administrator
from models import DeskflowRelay, DeskflowWorkbookArchive
from deskflow_archive import decrypt_archive

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
        return {**({'collected_at': None, 'categories': [], 'lots': [], 'progress': {'busy': False, 'phase': 'waiting', 'message': 'Waiting for the Windows desktop companion.'}} | data), 'desktop_connected': connected}


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
    if action not in ('collect', 'history', 'software-update') or payload != {}:
        raise HTTPException(400, 'Invalid Deskflow command.')
    with SessionLocal.begin() as session:
        row = _row(session)
        if not row.last_seen_at or (datetime.now(timezone.utc) - row.last_seen_at.replace(tzinfo=row.last_seen_at.tzinfo or timezone.utc)).total_seconds() >= 30:
            raise HTTPException(503, 'Open the SBCNAV desktop companion on the Windows PC to collect lots.')
        if row.command_id:
            raise HTTPException(409, 'A desktop command is already pending.')
        row.command_id = str(uuid4())
        row.command = {'action': action}
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
