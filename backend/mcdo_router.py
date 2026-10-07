"""MCDO: browser-authenticated IREPS evidence → Sheets → Oracle ledger."""
import base64
import os
import threading
from collections import Counter
from datetime import date, datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Query
from sqlalchemy import select, text, func
from database import SessionLocal, engine
from models import McdoSyncRun, ContractRegistryContract
from api_utils import envelope
from mcdo.core import actual, entered, key, day, relevant, invoice, contract_terms, latest_recorded_date
from mcdo.planner import main_plan
from mcdo.checkpoint import compatible, pending, seven_day_failures
from mcdo.sheets_api import Sheets, SOURCES, computed_workbook
from mcdo.auth import administrator, issue_session
from publicity_earnings import parse_workbook, read_ledger, dashboard, apply_import
from contract_registry import import_eauction_workbook, list_registry_contracts

router = APIRouter(prefix='/api/mcdo', tags=['MCDO'])

@router.post('/session',dependencies=[Depends(administrator)])
def start_session():
    return envelope(issue_session())

@router.get('/session',dependencies=[Depends(administrator)])
def session_status():
    return envelope({'authenticated':True})
CATEGORIES = ['Advertising','Misc-Static-Services','Misc-Mobile-Services','ATM/DBU/Banking e-Lobby','PMBJK','Parking','Hybrid NFR']
_worker_lock = threading.Lock()
_invalidate_cache = lambda: None

def configure_cache_invalidator(callback):
    global _invalidate_cache
    _invalidate_cache=callback

def today():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo('Asia/Kolkata')).date()

def find_run(session, run_id, lock=False):
    stmt=select(McdoSyncRun).where(McdoSyncRun.run_id==run_id)
    if lock: stmt=stmt.with_for_update()
    row=session.execute(stmt).scalar_one_or_none()
    if not row:raise HTTPException(404,'Sync run not found.')
    return row

def public_run(row):
    return {'run_id':row.run_id,'state':row.state,'mode':row.payload.get('mode','ireps'),'created_at':row.created_at,'updated_at':row.updated_at,'summary':row.payload.get('plan',{}).get('summary',{}),'warnings':row.payload.get('warnings',[]),'result':row.result,'error':row.error,'overdue':row.payload.get('overdue',[])}

def bridge_config(row):
    before=row.payload['before']
    invoices=[str(actual(r[19])) for r in before['earnings']['grid'] if len(r)>19 and str(actual(r[19])).startswith('ES')]
    due={key(actual(r[2])):actual(r[17]) for r in before['master']['grid'][1:] if len(r)>17 and actual(r[2]) and actual(r[17])}
    return {'run_id':row.run_id,'start':row.payload['start'],'end':row.payload['end'],'categories':CATEGORIES,'existing_invoices':invoices,'known_due':due}

@router.get('')
def mcdo(year: str | None=Query(None,pattern=r'^20\d{2}-\d{2}$')):
    with SessionLocal() as session:
        rows,source=read_ledger(session)
        counts=session.execute(select(ContractRegistryContract.status,func.count()).where(ContractRegistryContract.source_system=='e_auction').group_by(ContractRegistryContract.status)).all()
    data=dashboard(rows,source,year)
    return envelope({'earnings':data,'contracts':dict(counts),'sources':SOURCES,'configured':bool(os.getenv('MCDO_GOOGLE_CREDENTIALS')) and len(os.getenv('MCDO_ADMIN_TOKEN',''))>=32,'authentication':'IREPS digital-token sign-in in your browser'})

@router.post('/runs',dependencies=[Depends(administrator)])
def begin_run():
    sheets=Sheets()
    before={name:sheets.read(name) for name in SOURCES}
    latest=latest_recorded_date(before['earnings']['grid'])
    if latest>today():raise HTTPException(422,'Latest invoice is future-dated; review Main Sheet before syncing.')
    row=McdoSyncRun(run_id=str(uuid4()),state='awaiting_ireps',payload={'before':before,'start':latest.strftime('%d/%m/%Y'),'end':today().strftime('%d/%m/%Y')},result={})
    with SessionLocal.begin() as session:
        session.add(row);session.flush()
        result={**public_run(row),'connector':bridge_config(row)}
    return envelope(result)

@router.get('/runs',dependencies=[Depends(administrator)])
def runs():
    with SessionLocal() as session:
        rows=session.execute(select(McdoSyncRun).order_by(McdoSyncRun.created_at.desc()).limit(20)).scalars().all()
        return envelope([public_run(row) for row in rows])

@router.get('/runs/{run_id}',dependencies=[Depends(administrator)])
def get_run(run_id:str):
    with SessionLocal() as session:return envelope(public_run(find_run(session,run_id)))

def evidence_plan(payload, evidence):
    # The connector sends business evidence only. No session cookies, passwords or PINs.
    if set(evidence.get('completed_categories',[]))!=set(CATEGORIES):
        raise ValueError('IREPS category scan is incomplete; no spreadsheet writes were planned.')
    if evidence.get('start')!=payload['start'] or evidence.get('end')!=payload['end']:
        raise ValueError('IREPS scan date range differs from this preview.')
    statuses={}
    for item in evidence.get('contracts',[]):
        if not relevant(item['category']):continue
        k=key(item['contract'])
        if k in statuses and statuses[k]!=item:raise ValueError('Conflicting IREPS contract records.')
        statuses[k]=item
    if not statuses:raise ValueError('IREPS contract list is empty; check the authenticated account.')
    payments=[];paid_due={};seen={}
    for record in evidence.get('payments',[]):
        if not relevant(record['category']):continue
        inv=record['invoice']
        if inv in seen:
            if seen[inv]!=record:raise ValueError('Conflicting IREPS invoices.')
            continue
        seen[inv]=record
        if float(record['total'])>0:
            paid_due.setdefault(key(record['contract']),set()).add(day(record['due']))
        if not day(payload['start'])<=day(record['paid'])<=day(payload['end']):continue
        encoded=evidence.get('pdfs',{}).get(inv)
        if not encoded:continue
        pdf=base64.b64decode(encoded,validate=True)
        if len(pdf)>8*1024*1024 or not pdf.startswith(b'%PDF'):raise ValueError('Invalid or oversized invoice PDF.')
        payments.append(invoice(pdf,record))
    existing={str(actual(r[19])) for r in payload['before']['earnings']['grid'] if len(r)>19}
    needed={r['invoice'] for r in seen.values() if day(payload['start'])<=day(r['paid'])<=day(payload['end']) and r['invoice'] not in existing}
    if not needed.issubset({p['invoice'] for p in payments}):raise ValueError('A new collected invoice has no verified PDF.')
    terms={}
    for k,record in evidence.get('terms',{}).items():
        k=key(k)
        if k not in statuses:raise ValueError('Contract agreement is absent from the official list.')
        item=contract_terms(record['text'],record['schedule'],statuses[k]['contract'],statuses[k]['status'])
        item['paid_dates']=sorted(paid_due.get(k,set()))
        terms[k]=item
    required={key(p['contract']) for p in payments}
    for r in payload['before']['master']['grid'][1:]:
        if len(r)>17 and actual(r[2]) and actual(r[17]):
            k=key(actual(r[2]))
            if day(actual(r[17])) in paid_due.get(k,set()):required.add(k)
    if not required.issubset(terms):raise ValueError('Official agreement/schedule evidence is missing for a paid installment.')
    # A schedule-only update still needs a validated payment record for newly created contracts.
    payments.sort(key=lambda p:(day(p['paid']),p['invoice']))
    plan=main_plan(payload['before']['earnings']['grid'],payload['before']['master']['grid'],payments,terms,statuses,evidence.get('failures',[]),payload['end'])
    return plan

@router.post('/runs/{run_id}/evidence',dependencies=[Depends(administrator)])
async def submit_evidence(run_id:str,request:Request):
    raw=await request.body()
    if len(raw)>32*1024*1024:raise HTTPException(413,'IREPS evidence exceeds 32 MB.')
    import json
    try:evidence=json.loads(raw)
    except (ValueError,UnicodeError):raise HTTPException(422,'Invalid evidence JSON.')
    if not isinstance(evidence,dict):raise HTTPException(422,'Evidence must be a JSON object.')
    with SessionLocal.begin() as session:
        row=find_run(session,run_id,True)
        if row.state!='awaiting_ireps':raise HTTPException(409,'This run is no longer awaiting IREPS evidence.')
        if evidence.get('run_id')!=run_id:raise HTTPException(422,'IREPS evidence belongs to a different update run.')
        try:plan=evidence_plan(row.payload,evidence)
        except (ValueError,KeyError,TypeError,RuntimeError) as exc:raise HTTPException(422,str(exc)) from exc
        row.payload={**row.payload,'plan':plan,'warnings':evidence.get('warnings',[]),'overdue':seven_day_failures(plan['status'],row.payload['end'])}
        row.state='preview_ready'
        return envelope(public_run(row))

def checkpoint(run_id,state,result=None,error=None):
    with SessionLocal.begin() as session:
        row=find_run(session,run_id,True);row.state=state;row.error=error
        if result is not None:row.result=result
        row.updated_at=datetime.now(timezone.utc)

def import_sources(snapshots):
    master=computed_workbook('master',snapshots['master'])
    earnings=computed_workbook('earnings',snapshots['earnings'])
    parsed=parse_workbook(earnings)  # validate both complete sources before any DB import
    from contract_registry import parse_eauction_workbook
    contracts=parse_eauction_workbook(master)
    if not contracts or not parsed['rows']:raise RuntimeError('Source exports are empty; import refused.')
    result=import_eauction_workbook(master,source_file='Google Sheets: Master E Auction')
    with SessionLocal.begin() as session:
        ledger=apply_import(session,parsed,'Google Sheets: Earnings Master / Main Sheet')
    with SessionLocal() as session:
        registry={r.contract_number:r for r in session.execute(select(ContractRegistryContract).where(ContractRegistryContract.source_system=='e_auction')).scalars()}
        for source in contracts:
            live=registry.get(source['contract_number'])
            if not live or any(getattr(live,k)!=source[k] for k in ('status','policy_code','category','period_start','period_end')):
                raise RuntimeError('Oracle contract verification failed; resume the saved run.')
            for field in ('annual_license_fee','quarterly_license_fee','total_contract_value','additional_license_fee'):
                a,b=getattr(live,field),source[field]
                if (a is None)!=(b is None) or (a is not None and abs(float(a)-float(b))>=0.01):
                    raise RuntimeError('Oracle contract amount verification failed; resume the saved run.')
        persisted,metadata=read_ledger(session)
    if len(persisted)!=len(parsed['rows']):raise RuntimeError('Oracle earnings row count did not verify.')
    _invalidate_cache()
    return {'contracts':result,'earnings':ledger,'earnings_rows':len(parsed['rows'])}

def apply_worker(run_id,only_database=False):
    # One source writer across gunicorn processes; connection-scoped advisory lock.
    with _worker_lock, engine.connect() as connection:
        locked=False
        try:
            if engine.dialect.name=='postgresql':
                locked=connection.execute(text('SELECT pg_try_advisory_lock(74281031)')).scalar()
                if not locked:raise RuntimeError('Another MCDO update is running; resume after it finishes.')
            with SessionLocal() as session:
                row=find_run(session,run_id);payload=row.payload;result=dict(row.result)
            sheets=Sheets()
            if not only_database:
                if payload['end']!=today().strftime('%d/%m/%Y'):raise RuntimeError('This IREPS preview is from an earlier day. Start a fresh check.')
                # Check BOTH workbooks before the first write. A manual edit cannot be overwritten.
                current={name:sheets.read(name) for name in SOURCES}
                for name in SOURCES:
                    compatible(payload['before'][name]['grid'],current[name]['grid'],payload['plan'][name],SOURCES[name]['columns'])
                for name in SOURCES:
                    current[name]=sheets.read(name)
                    compatible(payload['before'][name]['grid'],current[name]['grid'],payload['plan'][name],SOURCES[name]['columns'])
                    todo=pending(payload['plan'][name],current[name]['grid'])
                    sheets.patches(name,current[name],todo,payload['plan']['formats'],payload['plan']['status'])
                    verified=sheets.read(name)
                    compatible(payload['before'][name]['grid'],verified['grid'],payload['plan'][name],SOURCES[name]['columns'])
                    if pending(payload['plan'][name],verified['grid']):raise RuntimeError(name+' sheet values did not verify. Resume this saved run.')
                    status=sheets.read(name,'IREPS Status Sync',10)
                    if pending([(1,1,payload['plan']['status'])],status['grid']):raise RuntimeError(name+' IREPS status report did not verify.')
                    result[name+'_verified']=True
                    checkpoint(run_id,'applying',result)
            snapshots={name:sheets.read(name) for name in SOURCES}
            if not only_database:
                for name in SOURCES:
                    compatible(payload['before'][name]['grid'],snapshots[name]['grid'],payload['plan'][name],SOURCES[name]['columns'])
                    if pending(payload['plan'][name],snapshots[name]['grid']):raise RuntimeError('A sheet changed before DB import; review the saved run.')
            result['database']=import_sources(snapshots)
            checkpoint(run_id,'complete',result)
        except Exception as exc:
            checkpoint(run_id,'needs_review',error=str(exc))
        finally:
            if locked:connection.execute(text('SELECT pg_advisory_unlock(74281031)'))

@router.post('/runs/{run_id}/apply',dependencies=[Depends(administrator)])
def apply(run_id:str,tasks:BackgroundTasks):
    with SessionLocal.begin() as session:
        row=find_run(session,run_id,True)
        if row.state not in ('preview_ready','needs_review'):raise HTTPException(409,'Only a reviewed preview or interrupted run can be applied.')
        only_database=row.payload.get('mode')=='sheets_to_oracle'
        if not only_database and 'plan' not in row.payload:raise HTTPException(409,'A validated IREPS preview is required.')
        row.state='applying';row.error=None
    tasks.add_task(apply_worker,run_id,only_database)
    return envelope({'run_id':run_id,'state':'applying'})

@router.post('/sync-sheets',dependencies=[Depends(administrator)])
def sync_existing_sheets(tasks:BackgroundTasks):
    row=McdoSyncRun(run_id=str(uuid4()),state='applying',payload={'mode':'sheets_to_oracle'},result={})
    with SessionLocal.begin() as session:session.add(row);session.flush();result=public_run(row)
    tasks.add_task(apply_worker,result['run_id'],True)
    return envelope(result)

@router.post('/runs/{run_id}/recover',dependencies=[Depends(administrator)])
def recover(run_id:str):
    with engine.connect() as connection:
        locked=False
        try:
            if engine.dialect.name=='postgresql':
                locked=connection.execute(text('SELECT pg_try_advisory_lock(74281031)')).scalar()
                if not locked:raise HTTPException(409,'The source updater is still running. Wait for it to finish.')
            with SessionLocal.begin() as session:
                row=find_run(session,run_id,True)
                last=row.updated_at.replace(tzinfo=timezone.utc) if row.updated_at.tzinfo is None else row.updated_at
                if row.state!='applying' or (datetime.now(timezone.utc)-last).total_seconds()<300:
                    raise HTTPException(409,'This run is still recent; wait at least five minutes before recovery.')
                row.state='needs_review';row.error='Interrupted run recovered. Review and resume the saved update.'
                return envelope(public_run(row))
        finally:
            if locked:connection.execute(text('SELECT pg_advisory_unlock(74281031)'))
