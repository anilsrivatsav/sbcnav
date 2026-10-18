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

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from sqlalchemy import select

from database import SessionLocal
from mcdo.auth import administrator
from models import DeskflowRelay

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
