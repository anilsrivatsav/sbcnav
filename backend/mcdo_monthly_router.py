"""Monthly MCDO completion, immutable history and Excel downloads."""
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api_utils import envelope
from database import SessionLocal
from models import McdoMonthlyPeriod, McdoMonthlyVersion, utcnow
from publicity_earnings import read_ledger
from mcdo.auth import administrator
from mcdo.monthly import ASSETS, MonthlyConfiguration, calculate, export_workbook, filename, period_dates

router = APIRouter(prefix='/api/mcdo/monthly', tags=['Monthly MCDO'])


def today():
    return datetime.now(ZoneInfo('Asia/Kolkata')).date()


def checked_period(period):
    try:
        return period_dates(period)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def version_info(row):
    return {'id': row.id, 'version': row.version, 'created_at': row.created_at.isoformat(),
            'fingerprint': row.fingerprint, 'filename': filename(row.snapshot, row.version)}


def versions(session, period):
    return session.scalars(select(McdoMonthlyVersion).where(McdoMonthlyVersion.period == period)
                           .order_by(McdoMonthlyVersion.version.desc())).all()


def report_state(session, period, rows, source):
    draft = session.get(McdoMonthlyPeriod, period)
    saved = versions(session, period)
    report = calculate(period, rows, source, draft.configuration if draft else {}, today())
    if saved and report['fingerprint'] == saved[0].fingerprint:
        report['status'] = 'Ready to Download'
    elif saved and report['status'] == 'Ready to Complete':
        report['status'] = 'Revision Ready'
    return {**report, 'revision': draft.revision if draft else 0,
            'versions': [version_info(v) for v in saved], 'asset_categories': ASSETS}


@router.get('')
def list_months(year: str | None = Query(None, pattern=r'^20\d{2}-\d{2}$')):
    with SessionLocal() as session:
        rows, source = read_ledger(session)
        years = {r['financial_year'] for r in rows}
        for period in session.scalars(select(McdoMonthlyPeriod.period)):
            years.add(checked_period(period)[3])
        now = today()
        y = now.year if now.month >= 4 else now.year - 1
        years.add(f'{y}-{(y+1)%100:02d}')
        selected = year or max(years)
        if int(selected[5:]) != (int(selected[:4])+1)%100:
            raise HTTPException(422, 'Invalid financial year.')
        months = []
        for m in list(range(4,13)) + [1,2,3]:
            period = f'{int(selected[:4]) + (m < 4)}-{m:02d}'
            state = report_state(session, period, rows, source)
            months.append({k: state[k] for k in ('period','month_name','status','pending','issues','versions')})
        return envelope({'years': sorted(years | {selected}), 'selected_year': selected, 'months': months})


@router.get('/{period}')
def get_month(period: str):
    checked_period(period)
    with SessionLocal() as session:
        rows, source = read_ledger(session)
        return envelope(report_state(session, period, rows, source))


class SaveDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=0)
    configuration: MonthlyConfiguration


@router.post('/{period}/draft', dependencies=[Depends(administrator)])
def save_draft(period: str, payload: SaveDraft):
    checked_period(period)
    with SessionLocal.begin() as session:
        draft = session.scalar(select(McdoMonthlyPeriod).where(McdoMonthlyPeriod.period == period).with_for_update())
        if not draft:
            # Database uniqueness also protects first-time creation races.
            if payload.expected_revision != 0:
                raise HTTPException(409, 'This month changed. Reload before saving.')
            draft = McdoMonthlyPeriod(period=period, revision=0, configuration={})
            try:
                with session.begin_nested():
                    session.add(draft)
                    session.flush()
            except IntegrityError:
                raise HTTPException(409, 'Another operator started this month. Reload before saving.') from None
        if draft.revision != payload.expected_revision:
            raise HTTPException(409, 'Another operator changed this month. Reload before saving.')
        draft.configuration = payload.configuration.model_dump(mode='json')
        draft.revision += 1
        draft.updated_at = utcnow()
        session.flush()
        rows, source = read_ledger(session)
        return envelope(report_state(session, period, rows, source))


class CompleteMonth(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')


@router.post('/{period}/complete', dependencies=[Depends(administrator)])
def complete_month(period: str, payload: CompleteMonth):
    checked_period(period)
    with SessionLocal.begin() as session:
        draft = session.scalar(select(McdoMonthlyPeriod).where(McdoMonthlyPeriod.period == period).with_for_update())
        if not draft:
            raise HTTPException(409, 'Save and validate the monthly inputs first.')
        rows, source = read_ledger(session)
        report = calculate(period, rows, source, draft.configuration, today())
        if report['fingerprint'] != payload.fingerprint:
            raise HTTPException(409, 'Source data or monthly inputs changed. Reload and validate again.')
        saved = versions(session, period)
        if report['issues'] or report['pending']:
            raise HTTPException(422, '; '.join(report['issues'] + report['pending']))
        if saved and saved[0].fingerprint == report['fingerprint']:
            return envelope(version_info(saved[0]))
        version = saved[0].version+1 if saved else 1
        row = McdoMonthlyVersion(id=str(uuid4()), period=period, version=version,
                                fingerprint=report['fingerprint'], snapshot=report,
                                workbook=export_workbook(report, version), created_at=utcnow())
        session.add(row)
        session.flush()
        return envelope(version_info(row))


@router.get('/{period}/download/{version_id}')
def download_month(period: str, version_id: str):
    checked_period(period)
    with SessionLocal() as session:
        row = session.get(McdoMonthlyVersion, version_id)
        if not row or row.period != period:
            raise HTTPException(404, 'Completed monthly report not found.')
        return Response(content=row.workbook,
                        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        headers={'Content-Disposition': f'attachment; filename="{filename(row.snapshot,row.version)}"',
                                 'Cache-Control': 'no-store'})
