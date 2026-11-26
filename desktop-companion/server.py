"""Loopback-only web controller for the proven Windows IREPS collector.

The operator credential is never returned as a JSON value. The explicit office-setup
download carries its private connection inside the installer. Only the configured
dashboard origin can invoke commands; no arbitrary URLs, files or scripts are accepted.
"""
import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / 'engine'))
import app
from core import day, key
from core import status_name
from web_incremental import watched_contracts, payment_queries
from ireps import Ireps, HOME, IncompleteResultsError
from playwright.sync_api import Error as BrowserError, TimeoutError as BrowserTimeout, sync_playwright
from state_store import read_state, write_state
from rp.setup_download import installer_path

PORT = 48722
ORIGIN = 'https://sbcnav-38t2.vercel.app'
ORIGINS = {ORIGIN, 'http://localhost:3000', 'http://localhost:3001'}
API = 'https://sbcnav.137-23-58-53.sslip.io/api/mcdo'
STATE = app.STATE / 'Web companion'
STATE.mkdir(parents=True, exist_ok=True)


def request(path, body=None):
    if not hasattr(request, '_gateway'):
        from mcdo_gateway import GatewayClient
        request._gateway = GatewayClient(STATE)
    return request._gateway.request(path, body)


class EvidenceReader(Ireps):
    """Retain original payment rows, including older paid dues, for server validation."""
    def __init__(self, *args):
        super().__init__(*args)
        self.observed = {}

    def all_rows(self, mode, filtered=False, max_rows=None):
        rows = super().all_rows(mode, filtered=filtered, max_rows=max_rows)
        if mode == 'paid':
            from urllib.parse import urljoin
            from core import relevant
            for row in rows:
                c = row['cells']
                if len(c) != 9 or not relevant(c[4]):
                    continue
                links = [a for a in row['links'] if re.fullmatch(r'ES\w+', a['text'])]
                if len(links) != 1:
                    raise RuntimeError('Missing unique invoice link.')
                match = re.search(r"window\.open\(\s*['\"]([^'\"]+)", links[0]['onclick'] or '')
                if not match:
                    raise RuntimeError('Invoice link format changed.')
                item = dict(invoice=links[0]['text'], url=urljoin(HOME, match[1]), paid=c[0],
                    total=float(c[1].replace(',', '')), contract=c[2], contract_date=c[3],
                    category=c[4], asset=c[5], firm=c[6], due=c[7])
                old = self.observed.get(item['invoice'])
                if old is not None and old != item:
                    raise RuntimeError('Conflicting duplicate invoice rows.')
                self.observed[item['invoice']] = item
        return rows


def collector_due_dates(values):
    """Oracle sends Sheet serials; the desktop collector compares Python dates."""
    return {key(contract): day(value) if value not in (None, '') else None
            for contract, value in values.items()}


class Controller:
    def __init__(self):
        self.lock = threading.RLock()
        self.gate = threading.Event()
        self.gate.set()
        self.thread = None
        self.state = {'phase': 'ready', 'message': 'Ready to update.', 'run': None, 'logs': []}
        try:
            self.state.update(read_state(STATE / 'state.json'))
            if self.state['phase'] not in ('ready', 'complete', 'error'):
                self.state.update(phase='interrupted', message='The computer restarted. Resume checks saved progress before continuing.')
        except (OSError, ValueError):
            pass

    def save(self, **values):
        with self.lock:
            self.state.update(values)
            self.state.pop('persistence_warning', None)
            if write_state(STATE / 'state.json', self.state):
                self.state['persistence_warning'] = 'Windows locked the main progress file. Progress is safely saved in a recovery checkpoint.'

    def snapshot(self):
        with self.lock:
            deskflow_instance = globals().get('deskflow')
            deskflow_busy = bool(deskflow_instance and deskflow_instance.thread and deskflow_instance.thread.is_alive())
            return {**self.state, 'busy': bool(self.thread and self.thread.is_alive()),
                    'deskflow_busy': deskflow_busy,
                    'connected': True, 'version': '2.2.1', 'configured': (STATE / 'operator.key').exists(),
                    'monthly_reports': True, 'inventory_retry': True, 'adaptive_retry': True,
                    'incremental_updates': True,
                    'installer_available': installer_path(STATE) is not None}

    def log(self, message):
        message = str(message).split('\nCall log:', 1)[0]
        with self.lock:
            self.save(message=message, logs=(self.state['logs'] + [app.now().strftime('%H:%M:%S') + ' ' + message])[-100:])

    def checkpoint(self):
        self.gate.wait()
        return False

    def command(self, action):
        with self.lock:
            process = globals().get('software_update_process')
            if process and process.poll() is None:
                raise RuntimeError('The desktop companion is updating. Wait for it to finish.')
            if 'deskflow' in globals() and deskflow.thread and deskflow.thread.is_alive():
                raise RuntimeError('Deskflow is collecting IREPS evidence. Wait for it to finish.')
            active = self.thread and self.thread.is_alive()
            if action == 'pause':
                if not active:
                    raise RuntimeError('There is no active update to pause.')
                if self.state['phase'] == 'applying':
                    request('/runs/' + self.state['run']['run_id'] + '/pause', {})
                    self.save(message='Pausing after the current write is verified.')
                else:
                    self.gate.clear()
                    self.save(phase='paused', message='Paused. Resume continues the same scan.')
                return
            if action == 'resume' and active:
                if self.gate.is_set():
                    raise RuntimeError('An update is already running.')
                self.save(phase='collecting', message='Continuing the saved scan.')
                self.gate.set()
                return
            if active:
                raise RuntimeError('An update is already running.')
            if action not in ('start', 'resume', 'sync', 'inventory'):
                raise RuntimeError('Unknown updater action.')
            if not (STATE / 'operator.key').exists():
                raise RuntimeError('This computer needs administrator setup.')
            self.gate.set()
            if action != 'resume':
                self.save(scan_action=action)
            self.save(phase='connecting', error=None, message='Checking connection and saved progress…')
            self.thread = threading.Thread(target=self.work, args=(action,), daemon=True)
            self.thread.start()

    def monitor(self, run):
        while run['state'] == 'applying':
            self.save(phase='applying', run=run, message='Updating and verifying both Sheets and Oracle…')
            time.sleep(3)
            run = request('/runs/' + run['run_id'])
        self.save(run=run)
        if run['state'] == 'complete':
            report = (run.get('result') or {}).get('monthly_report') or {}
            message = 'Both Sheets and Oracle are verified.'
            if any(w.startswith('Full contract inventory deferred:') for w in run.get('warnings', [])):
                message += ' Receipts and Master changes were applied. Full contract verification needs a retry.'
            if report.get('status') == 'Ready to Download':
                message += f" MCDO workbook for {report['period']} is ready to download."
            elif report:
                message += f" MCDO workbook for {report['period']} needs attention. See Monthly MCDO for details."
            self.save(phase='complete', message=message, error=None)
        elif run['state'] == 'paused':
            self.save(phase='paused', message='Paused at a verified checkpoint. Choose Resume.')
        else:
            raise RuntimeError(run.get('error') or 'Update needs review. Saved progress is retained.')

    def work(self, action):
        try:
            request('/session')
            saved = self.state.get('run')
            if action == 'resume' and saved:
                run = request('/runs/' + saved['run_id'])
                retry_action = self.state.get('scan_action', 'start')
                if retry_action not in ('start', 'inventory'):
                    retry_action = 'start'
                if run['state'] == 'awaiting_ireps':
                    saved_evidence = read_state(STATE / (run['run_id'] + '.json'))
                    inventory_pending = retry_action == 'inventory' and not saved_evidence.get('contract_reconciliation')
                    if saved_evidence.get('end') == app.now().strftime('%d/%m/%Y') and not inventory_pending:
                        run = request('/runs/' + run['run_id'] + '/evidence', saved_evidence)
                    else:
                        action = retry_action
                        self.log('Reopening IREPS to resume the interrupted read.')
                if action == 'resume':
                    if run['state'] in ('preview_ready', 'needs_review', 'paused'):
                        request('/runs/' + run['run_id'] + '/apply', {})
                        run = request('/runs/' + run['run_id'])
                    self.monitor(run)
                    return
            if action == 'sync':
                self.monitor(request('/sync-sheets', {}))
                return
            # Never silently replace an unfinished server write.
            recent_runs = request('/runs')
            for old in recent_runs:
                if old['state'] == 'applying':
                    self.save(run=old)
                    self.monitor(old)
                    return
            run = request('/runs', {'scan_mode': 'full' if action == 'inventory' else 'incremental'})
            self.save(run=run, start=run['connector']['start'], end=run['connector']['end'])
            cfg = run['connector']
            checked = self.recent_receipt_evidence(recent_runs, cfg) if action == 'inventory' else None
            for attempt in range(2):
                try:
                    evidence = self.collect_ireps_evidence(run['run_id'], cfg, action, checked, saved)
                    break
                except BrowserError as exc:
                    reconnect = isinstance(exc, BrowserTimeout) or 'Target page, context or browser has been closed' in str(exc)
                    if not reconnect:
                        raise
                    if attempt:
                        raise RuntimeError('IREPS did not answer after reconnecting. Choose Retry MCDO update when IREPS is available.') from exc
                    self.log('IREPS stopped responding. Reopening the updater browser and retrying automatically.')
            self.checkpoint()
            self.save(phase='validating', message='Validating invoices and official schedules before writes…')
            run = request('/runs/' + run['run_id'] + '/evidence', evidence)
            self.save(run=run)
            self.checkpoint()
            request('/runs/' + run['run_id'] + '/apply', {})
            self.monitor(request('/runs/' + run['run_id']))
        except Exception as exc:
            # Do not expose Playwright request diagnostics, which may include cookies.
            message = str(exc).split('\nCall log:', 1)[0][:1500]
            self.save(phase='error', error=message, message='Update stopped. Verified work and complete evidence are saved.')

    def collect_ireps_evidence(self, run_id, cfg, action, checked, saved):
        evidence_path = STATE / (run_id + '.json')
        contract_path = STATE / ('contracts-' + run_id + '.json')
        with sync_playwright() as pw:
            browser = app.browser(pw, {'ireps_only': True}, self.log)
            reader = EvidenceReader(browser.contexts[0], self.log, self.checkpoint)
            try:
                self.save(phase='login', message='Opening IREPS in the updater Chrome window. Sign in with your digital token if prompted.')
                reader.page.bring_to_front()
                reader.login()
                self.save(phase='collecting')
                evidence = read_state(evidence_path)
                if not evidence and checked:
                    self.log('Using receipts already verified today. Starting a fresh contract inventory.')
                    evidence = {**checked, 'run_id':run_id, 'start':cfg['start']}
                    evidence.pop('contract_reconciliation', None)
                if not evidence:
                    evidence = self.collect_receipts(reader, run_id, cfg, saved)
                if not cfg.get('full_contract_reconciliation'):
                    write_state(evidence_path, evidence)
                    return evidence
                from contract_collector import collect_inventory
                evidence['warnings'] = [*reader.warnings,
                    'Full contract inventory deferred: only complete receipts and Master evidence was saved.']
                write_state(evidence_path, evidence)
                options = {'master_contracts': set(cfg['master_contracts'])} if 'master_contracts' in cfg else {}
                previous = read_state(contract_path)
                if not previous and action == 'inventory' and saved:
                    previous = read_state(STATE / ('contracts-' + saved['run_id'] + '.json'))
                    if previous.get('collection_complete'):
                        previous = {}
                if previous and previous.get('asof') == cfg['end']:
                    options['previous'] = previous
                    write_state(contract_path, previous)
                    self.log(f"Resuming today's contract checkpoint with {len(previous['completed_categories'])} categories already checked.")
                try:
                    reconciliation = collect_inventory(reader, self, cfg['end'],
                                                       lambda data: write_state(contract_path, data), **options)
                except (BrowserTimeout, IncompleteResultsError) as exc:
                    if action == 'inventory':
                        self.log('Saved the contract inventory checkpoint. Retry continues from the last checked category.')
                        raise
                    reason = str(exc).split('\nCall log:', 1)[0]
                    warning = ('Full contract inventory deferred: IREPS pagination or navigation '
                               'failed. The completed receipts and Master check will continue. ' + reason)
                    evidence['warnings'] = [*reader.warnings, warning]
                    self.log(warning)
                else:
                    evidence['contract_reconciliation'] = reconciliation
                    evidence['warnings'] = list(dict.fromkeys([*reader.warnings, *reconciliation.get('warnings', [])]))
                write_state(evidence_path, evidence)
                return evidence
            finally:
                with suppress(BrowserError):
                    reader.page.close()

    def recent_receipt_evidence(self, runs, cfg):
        existing = set(cfg['existing_invoices'])
        for run in runs:
            if run.get('state') != 'complete' or not (run.get('result') or {}).get('earnings_verified'):
                continue
            try:
                evidence = read_state(STATE / (run['run_id'] + '.json'))
                if (evidence.get('end') == cfg['end'] and day(evidence['start']) <= day(cfg['start'])
                        and set(evidence['completed_categories']) == set(cfg['categories'])
                        and set(evidence.get('pdfs', {})).issubset(existing)):
                    return evidence
            except (OSError, ValueError, KeyError):
                continue
        return None

    def collect_receipts(self, reader, run_id, cfg, saved):
        categories = cfg['categories']
        scope = {name:cfg[name] for name in ('start','end','categories','existing_invoices','known_due')}
        incremental = cfg.get('scan_mode') == 'incremental'
        if incremental:
            if 'master_watch' not in cfg:
                raise RuntimeError('Update the SBC NAV backend before using incremental collection.')
            scope.update(scan_mode='incremental', master_watch=cfg['master_watch'], contracts_since=cfg['contracts_since'])
        progress_path = STATE / ('receipts-' + run_id + '.json')
        progress = read_state(progress_path)
        if not progress and saved and saved.get('state') == 'awaiting_ireps':
            progress = read_state(STATE / ('receipts-' + saved['run_id'] + '.json'))
        if progress.get('scope') != scope:
            progress = {'scope':scope}
        elif 'statuses' in progress:
            write_state(progress_path, progress)
            self.log('Continuing from verified IREPS read stages already saved for this update.')
        if 'failures' not in progress:
            progress['failures'] = reader.failures(categories)
            write_state(progress_path, progress)
        if 'statuses' not in progress:
            if incremental and 'discovered_statuses' not in progress:
                self.log('Routine update: recent awards, watched active contracts and pending dues. Full history is skipped.')
                statuses = reader.contracts(categories, cfg['contracts_since'], cfg['end'])
                progress['discovered_statuses'] = statuses
                write_state(progress_path, progress)
            elif not incremental:
                progress['statuses'] = reader.contracts(categories, '01/01/2020', cfg['end'])
                write_state(progress_path, progress)
        if incremental and 'statuses' not in progress:
            statuses = progress['discovered_statuses']
            for k, contract in sorted(watched_contracts(cfg, progress['failures']).items()):
                if k not in statuses:
                    statuses[k] = reader.contract_record(contract, cfg['end'])
                    progress['discovered_statuses'] = statuses
                    write_state(progress_path, progress)
            progress['statuses'] = statuses
            write_state(progress_path, progress)
        if 'records' not in progress:
            queries = payment_queries(cfg, progress['statuses'], progress['failures']) if incremental else None
            progress['records'] = reader.payments(categories, cfg['start'], cfg['end'],
                queries=queries,
                existing=set(cfg['existing_invoices']), known_due=collector_due_dates(cfg['known_due']))
            progress['observed'] = list(reader.observed.values())
            progress['paid_due'] = {contract:sorted(value.isoformat() for value in dates)
                                    for contract, dates in reader.confirmed_paid_due.items()}
            write_state(progress_path, progress)
        statuses, failures, records = (progress[name] for name in ('statuses','failures','records'))
        pdfs = {}
        folder = STATE / ('Invoices-' + run_id)
        folder.mkdir(exist_ok=True)
        for record in records:
            self.checkpoint()
            self.log('Verifying invoice ' + record['invoice'])
            pdfs[record['invoice']] = base64.b64encode(reader.download(record, folder / (record['invoice'] + '.pdf'))).decode()
        wanted = {key(r['contract']) for r in records}
        if incremental:
            known = set(cfg['master_contracts'])
            wanted.update(k for k, r in statuses.items()
                          if k not in known and status_name(r['status']) == 'Running')
        for contract, due in cfg['known_due'].items():
            if day(due).isoformat() in progress['paid_due'].get(key(contract), ()):
                wanted.add(key(contract))
        terms = {}
        for contract in sorted(wanted):
            self.checkpoint()
            if contract not in statuses:
                raise RuntimeError('Paid contract is absent from the official contract list: ' + contract)
            self.log('Checking official unpaid schedule: ' + statuses[contract]['contract'])
            terms[contract] = reader.terms({**statuses[contract], 'asof': cfg['end']}, raw=True)
        result = dict(run_id=run_id, start=cfg['start'], end=cfg['end'], completed_categories=categories,
                    contracts=list(statuses.values()), payments=progress['observed'], failures=failures,
                    terms=terms, pdfs=pdfs, warnings=reader.warnings)
        if incremental:
            result['contract_updates'] = {'contracts': list(statuses.values()), 'payments': progress['observed'],
                'details': {k: {'agreement': v['text'], 'schedule': v['schedule']} for k, v in terms.items()}}
            # Unpaid awards are handled by the agreement-backed award path, which
            # permits a marked preview when the master has room for only 19 dues.
            required = {key(r['contract']) for r in records}
            required.update(key(c) for c, d in cfg['known_due'].items()
                            if day(d).isoformat() in progress['paid_due'].get(key(c), ()))
            result['terms'] = {k: v for k, v in terms.items() if k in required}
        return result


controller = Controller()
from deskflow import Deskflow, public_text
deskflow = Deskflow(controller, app, sync_playwright, Ireps)


class WorkbookArchiveSync:
    """Send selected workbook snapshots to the encrypted Oracle archive."""
    def __init__(self):
        self.lock = threading.Lock()
        self.thread = None
        self.path = STATE / 'workbook-sync.json'
        try:
            self.state = read_state(self.path)
        except (OSError, ValueError):
            self.state = {}
        self.state.setdefault('phase', 'waiting')
        self.state.setdefault('message', 'Waiting for selected workbooks on this PC.')
        previous=deskflow.store.evidence('__workspace__','workbook_update')
        if previous:
            report=previous[-1]
            if report.get('at','')>=self.state.get('writeback',{}).get('at',''):
                self.state['writeback']={'files':report.get('saved',[]),'calculated':report.get('calculated',0),'pending':len(report.get('pending',[])),'at':report.get('at')}

    def snapshot(self):
        with self.lock:
            return {**self.state, 'busy': bool(self.thread and self.thread.is_alive())}

    def save(self, **changes):
        with self.lock:
            self.state.update(changes)
            write_state(self.path, self.state)

    def start(self, force=False, update_local=False, reviewed_only=False):
        with self.lock:
            if self.thread and self.thread.is_alive():
                if force:
                    raise RuntimeError('Workbook sync is already running.')
                return
            if not (STATE / 'operator.key').is_file():
                if force:
                    raise RuntimeError('This computer needs administrator setup.')
                return
            if not update_local and not reviewed_only and (controller.snapshot()['busy'] or (deskflow.thread and deskflow.thread.is_alive())):
                return
            if update_local or reviewed_only:
                with controller.lock, deskflow.lock:
                    if controller.snapshot()['busy'] or (deskflow.thread and deskflow.thread.is_alive()):
                        raise RuntimeError('Finish the current IREPS collection before syncing Excel and the website.')
                    from rp.workbooks import WorkbookSelection
                    selection=WorkbookSelection(deskflow.userdir/'workbooks.json')
                    for group in ('commercial','parcel','catering'):
                        path=selection.target('D:/ANIL/UK',group)
                        if path.with_name('~$'+path.name).exists():
                            raise RuntimeError('Save and close this workbook in Excel before two-way sync: '+path.name)
                    self.thread=threading.Thread(target=self.work,args=(force,update_local,reviewed_only),daemon=True)
                    deskflow.thread=self.thread
            else:
                self.thread = threading.Thread(target=self.work, args=(force,False), daemon=True)
            self.thread.start()

    def work(self, force, update_local=False, reviewed_only=False):
        from rp.workbooks import WorkbookSelection
        try:
            if update_local or reviewed_only:
                self.save(phase='collecting',message='Collecting IREPS lots and updating the selected Excel files before uploading the website copy.',error=None)
                report=deskflow.write_workbooks(ready_only=True) if reviewed_only else deskflow.update_workbooks()
                if not report or deskflow.state.get('error'):
                    raise RuntimeError(deskflow.state.get('error') or 'Excel update did not complete. Website upload stopped.')
                self.save(writeback={'files':report['saved'],'calculated':report['calculated'],'pending':len(report['pending']),'at':report['at']})
                if reviewed_only:
                    state=dict(deskflow.state);deskflow.import_baseline();deskflow.state.update(state)
            self.save(phase='checking', message='Checking selected local workbooks.', error=None)
            selection = WorkbookSelection(deskflow.userdir / 'workbooks.json')
            names = {'parcel': 'parcels.xlsx', 'catering': 'catering.xlsx', 'commercial': 'others.xlsx'}
            data = {}
            for group, name in names.items():
                path = selection.target('D:/ANIL/UK', group)
                data[name] = path.read_bytes()
            digest = hashlib.sha256(b''.join(hashlib.sha256(data[name]).digest() for name in sorted(data))).hexdigest()
            if not force and digest == self.snapshot().get('digest'):
                last=self.snapshot().get('writeback')
                message='Website archive matches the saved Excel files.'
                if last:message+=f" Last Excel update: {len(last['files'])} files saved at {last['at']}."
                else:message+=' Excel write-back has not run yet.'
                self.save(phase='complete', message=message, error=None)
                return
            memory = io.BytesIO()
            with zipfile.ZipFile(memory, 'w', compression=zipfile.ZIP_DEFLATED) as package:
                for name, content in data.items():
                    package.writestr(name, content)
            bundle = memory.getvalue()
            if len(bundle) > 8_000_000:
                raise RuntimeError('Selected workbooks exceed the 8 MB upload limit.')
            self.save(phase='uploading', message='Updating the encrypted workbook archive.')
            credential = (STATE / 'operator.key').read_text(encoding='utf-8').strip()
            endpoint = API.rsplit('/', 1)[0] + '/deskflow/agent/workbook-archive'
            req = urllib.request.Request(endpoint, data=bundle,
                headers={'Authorization': 'Bearer ' + credential, 'Content-Type': 'application/zip'})
            try:
                with urllib.request.urlopen(req, timeout=120) as response:
                    result = json.load(response)
            except urllib.error.HTTPError as exc:
                try:
                    detail = json.load(exc).get('detail', 'Workbook archive update failed.')
                except (OSError, ValueError):
                    detail = 'Workbook archive update failed.'
                raise RuntimeError(str(detail)) from None
            message='Saved Excel files uploaded to the website archive.'
            if update_local:message=f"Two-way sync complete: {len(report['saved'])} Excel files updated with backups; the website archive now matches the saved files."
            elif self.snapshot().get('writeback'):
                last=self.snapshot()['writeback'];message+=f" Last Excel update: {len(last['files'])} files saved at {last['at']}."
            self.save(phase='complete', message=message,
                digest=digest, revision=result['generatedAt'], rows=result['totalRows'],
                records=result['auctionRecordCount'], error=None)
        except Exception as exc:
            self.save(phase='error', message='Workbook sync needs attention.', error=str(exc)[:500])


archive_sync = WorkbookArchiveSync()


class DeskflowAccess:
    def __init__(self):
        self.lock = threading.Lock()
        self.sessions = {}
        self.attempts = {}
        self.password_digest = hashlib.sha256(b'Antara').digest()

    def unlock(self, password, address):
        with self.lock:
            now = time.monotonic()
            attempts = [t for t in self.attempts.get(address, []) if now - t < 60]
            if len(attempts) >= 5:
                raise ValueError('Too many attempts. Try again in a minute.')
            if not isinstance(password, str) or not hmac.compare_digest(hashlib.sha256(password.encode()).digest(), self.password_digest):
                self.attempts[address] = attempts + [now]
                raise ValueError('Incorrect password.')
            self.attempts.pop(address, None)
            token = secrets.token_urlsafe(32)
            self.sessions = {t: expiry for t, expiry in self.sessions.items() if expiry > now}
            self.sessions[token] = now + 3600
            return token

    def permitted(self, header):
        if not header.startswith('Bearer '): return False
        with self.lock:
            return self.sessions.get(header[7:], 0) > time.monotonic()


deskflow_access = DeskflowAccess()

software_update_process = None


def software_update_running():
    return bool(software_update_process and software_update_process.poll() is None)


def software_update_status():
    path = STATE / 'software-update.json'
    try:
        result = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(result, dict): raise ValueError('Invalid update state.')
    except (OSError, ValueError):
        result = {'phase': 'ready', 'message': 'Ready to check for a desktop update.'}
    revision = STATE / '.installed-commit'
    try:
        result['revision'] = revision.read_text(encoding='utf-8').strip()[:7]
    except OSError:
        result['revision'] = None
    return result


def start_software_update():
    global software_update_process
    with controller.lock, deskflow.lock:
        if (controller.thread and controller.thread.is_alive()) or (deskflow.thread and deskflow.thread.is_alive()):
            raise RuntimeError('Wait for the current MCDO or Deskflow work to finish.')
        if software_update_running():
            raise RuntimeError('A desktop update is already running.')
        if getattr(sys, 'frozen', False):
            import webbrowser
            webbrowser.open('https://github.com/anilsrivatsav/sbcnav/releases/latest')
            result = {'phase': 'ready', 'message': 'Download and run the latest SBC NAV Windows installer. Your saved connection and progress are kept.'}
            write_state(STATE / 'software-update.json', result)
            return result
        script = BASE / 'update.ps1'
        if not script.is_file():
            raise RuntimeError('The desktop updater is not installed. Run the one-time setup on this PC.')
        (STATE / 'software-update.json').write_text(json.dumps({
            'phase': 'starting', 'message': 'Checking GitHub for the latest desktop version…'
        }), encoding='utf-8')
        try:
            software_update_process = subprocess.Popen(
                ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
                cwd=str(BASE), creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            raise RuntimeError('Could not start the desktop updater on this PC.') from exc
    return software_update_status()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def permitted(self):
        return self.headers.get('Host') == f'127.0.0.1:{PORT}' and self.headers.get('Origin') in ORIGINS

    def deskflow_permitted(self):
        return deskflow_access.permitted(self.headers.get('Authorization', ''))

    def respond(self, status, value):
        if self.path.startswith('/deskflow/'):
            value=public_text(value)
        self.send_response(status)
        if self.permitted():
            self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin'))
            self.send_header('Vary', 'Origin')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(json.dumps(value).encode())

    def do_OPTIONS(self):
        self.respond(204 if self.permitted() else 403, {})

    def do_GET(self):
        if not self.permitted():
            return self.respond(403, {'error': 'Origin not allowed.'})
        if self.path.startswith('/deskflow/') and not self.deskflow_permitted():
            return self.respond(401, {'error': 'Unlock Deskflow first.'})
        if self.path == '/deskflow/overview':
            return self.respond(200, deskflow.overview())
        if self.path == '/deskflow/progress':
            return self.respond(200, deskflow.progress())
        if self.path == '/deskflow/status':
            return self.respond(200, deskflow.snapshot())
        if self.path == '/deskflow/software-update':
            return self.respond(200, software_update_status())
        if self.path != '/status':
            return self.respond(404, {'error': 'Not found.'})
        self.respond(200, controller.snapshot())

    def do_POST(self):
        if not self.permitted() or self.headers.get('Content-Type') != 'application/json':
            return self.respond(403, {'error': 'Origin or content type not allowed.'})
        if self.path == '/monthly-report':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 20000:
                    raise ValueError('Invalid monthly report request size.')
                data = json.loads(self.rfile.read(length))
                return self.respond(200, monthly_report_command(data))
            except (ValueError, KeyError, TypeError, RuntimeError) as exc:
                return self.respond(400, {'error': str(exc)})
        if self.path == '/windows-setup':
            if self.headers.get('Origin') != ORIGIN:
                return self.respond(403, {'error': 'The private installer is available only from the SBC NAV production page.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 256 or json.loads(self.rfile.read(length)) != {}:
                    return self.respond(400, {'error': 'Expected an empty JSON object.'})
                path = installer_path(STATE)
                if path is None:
                    return self.respond(404, {'error': 'The ready-to-use office installer is not available on this PC yet.'})
                import shutil
                with path.open('rb') as stream:
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin'))
                    self.send_header('Vary', 'Origin')
                    self.send_header('Content-Type', 'application/vnd.microsoft.portable-executable')
                    self.send_header('Content-Disposition', 'attachment; filename="' + path.name + '"')
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.send_header('Content-Length', str(path.stat().st_size))
                    self.end_headers()
                    shutil.copyfileobj(stream, self.wfile, length=1024 * 1024)
                return
            except (ValueError, OSError):
                return self.respond(400, {'error': 'The installer download could not finish. Retry the download.'})
        if self.path.startswith('/deskflow/'):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2_000_000: raise ValueError('Invalid request size.')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict): raise ValueError('Expected a JSON object.')
                if self.path == '/deskflow/unlock':
                    return self.respond(200, {'token':deskflow_access.unlock(data.get('password'), self.client_address[0])})
                if not self.deskflow_permitted():
                    return self.respond(401, {'error':'Unlock Deskflow first.'})
                if self.path == '/deskflow/software-update':
                    if data != {}: raise ValueError('Expected an empty JSON object.')
                    return self.respond(202, start_software_update())
                if self.path == '/deskflow/save-reviewed':
                    if data != {}:raise ValueError('Expected an empty JSON object.')
                    archive_sync.start(force=True,reviewed_only=True)
                    return self.respond(200,deskflow.progress())
                with controller.lock, deskflow.lock:
                    if software_update_running():
                        raise RuntimeError('The desktop companion is updating. Wait for it to finish.')
                    return self.respond(200, deskflow.command(self.path.rsplit('/',1)[-1], data))
            except (ValueError, KeyError, TypeError, RuntimeError) as exc:
                return self.respond(400, {'error': str(exc)})
        if self.path not in ('/start', '/resume', '/pause', '/sync', '/inventory'):
            return self.respond(404, {'error': 'Not found.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 256 or json.loads(self.rfile.read(length)) != {}:
                return self.respond(400, {'error': 'Expected an empty JSON object.'})
            controller.command(self.path[1:])
            self.respond(202, controller.snapshot())
        except (ValueError, RuntimeError) as exc:
            self.respond(409, {'error': str(exc)})


def monthly_report_command(data):
    """Two fixed authenticated report operations; the private key stays on this PC."""
    if not isinstance(data, dict) or set(data) != {'period', 'action', 'payload'}:
        raise ValueError('Invalid monthly report command.')
    period, action, payload = data['period'], data['action'], data['payload']
    if not isinstance(period, str) or not re.fullmatch(r'20\d{2}-(?:0[1-9]|1[0-2])', period):
        raise ValueError('Invalid report month.')
    if action not in ('draft', 'complete') or not isinstance(payload, dict):
        raise ValueError('Unknown monthly report action.')
    return request('/monthly/' + period + '/' + action, payload)


def deskflow_relay_loop():
    """Connect the local collector to the browser through the authenticated API."""
    endpoint = API.rsplit('/', 1)[0] + '/deskflow/agent/sync'
    ack_path = STATE / 'deskflow-command-ack.json'
    last_archive_check = 0.0
    while True:
        try:
            credential = (STATE / 'operator.key').read_text(encoding='utf-8').strip()
            try:
                ack = json.loads(ack_path.read_text(encoding='utf-8')).get('command_id')
            except (OSError, ValueError):
                ack = None
            overview = public_text(deskflow.overview())
            overview['schedule_pdf_requests'] = deskflow.schedule_pdf_status()
            from rp.asset_library import snapshot as asset_snapshot
            overview['analysis_library'] = asset_snapshot(deskflow.store)
            overview['archive_sync'] = public_text(archive_sync.snapshot())
            payload = {'overview': overview,
                       'software_update': software_update_status(),
                       'ack_command_id': ack}
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(),
                headers={'Authorization': 'Bearer ' + credential, 'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=20) as response:
                command = json.load(response)
            if not software_update_running() and time.monotonic() - last_archive_check >= 60:
                last_archive_check = time.monotonic()
                archive_sync.start()
            command_id = command.get('command_id')
            if command_id and command_id != ack:
                # Record the command before executing: updates can restart this process.
                ack_path.write_text(json.dumps({'command_id': command_id}), encoding='utf-8')
                try:
                    if command.get('action') == 'software-update':
                        start_software_update()
                    elif command.get('action') == 'sync-workbooks':
                        if software_update_running():
                            raise RuntimeError('The desktop companion is updating. Wait for it to finish.')
                        archive_sync.start(force=True,update_local=True)
                    elif command.get('action') == 'save-reviewed':
                        archive_sync.start(force=True,reviewed_only=True)
                    elif command.get('action') == 'schedule-pdf':
                        with controller.lock, deskflow.lock:
                            if software_update_running():
                                raise RuntimeError('The desktop companion is updating. Wait for it to finish.')
                            deskflow.command('schedule-pdf', {'request_id': command_id})
                    elif command.get('action') in ('collect', 'history','link-asset','save-review','review-proposal','cancel'):
                        with controller.lock, deskflow.lock:
                            if software_update_running():
                                raise RuntimeError('The desktop companion is updating. Wait for it to finish.')
                            deskflow.command(command['action'], command.get('payload',{}))
                except (ValueError, RuntimeError) as exc:
                    if command.get('action') == 'schedule-pdf':
                        deskflow.set_schedule_pdf(command_id, phase='error', message=str(exc))
                    else:
                        deskflow.state.update(phase='error', error=str(exc), message='Deskflow command could not start.')
        except Exception:
            pass  # Retain local collection and retry when the API is available.
        time.sleep(8)


class SingleCompanionServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        import socket
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def serve():
    # Bind first. A second Windows process must not run another relay or scan
    # while a companion already owns the local endpoint.
    server = SingleCompanionServer(('127.0.0.1', PORT), Handler)
    threading.Thread(target=deskflow_relay_loop, daemon=True).start()
    threading.Thread(target=daily_routine_loop, daemon=True).start()
    server.serve_forever()


def daily_routine_loop():
    from daily_routine import tick
    while True:
        try:
            if not software_update_running():
                tick(controller, deskflow, STATE / 'daily-routine.json')
        except Exception:
            pass  # Preserve the checkpoint; interactive actions remain available.
        time.sleep(60)


if __name__ == '__main__':
    serve()
