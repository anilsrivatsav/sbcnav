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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / 'engine'))
import app
from core import day, key
from ireps import Ireps, HOME
from playwright.sync_api import sync_playwright
from state_store import read_state, write_state
from rp.setup_download import installer_path

PORT = 48722
ORIGIN = 'https://sbcnav-38t2.vercel.app'
ORIGINS = {ORIGIN, 'http://localhost:3000', 'http://localhost:3001'}
API = 'https://sbcnav.137-23-58-53.sslip.io/api/mcdo'
STATE = app.STATE / 'Web companion'
STATE.mkdir(parents=True, exist_ok=True)


def request(path, body=None):
    token = (STATE / 'operator.key').read_text(encoding='utf-8').strip()
    req = urllib.request.Request(API + path, data=None if body is None else json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)['data']
    except urllib.error.HTTPError as exc:
        try:
            message = json.load(exc).get('detail', 'Oracle request failed.')
        except (ValueError, OSError):
            message = 'Oracle request failed.'
        raise RuntimeError(str(message)) from None


class EvidenceReader(Ireps):
    """Retain original payment rows, including older paid dues, for server validation."""
    def __init__(self, *args):
        super().__init__(*args)
        self.observed = {}

    def all_rows(self, mode, filtered=False):
        rows = super().all_rows(mode, filtered)
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
                    'connected': True, 'version': '2.2.0', 'configured': (STATE / 'operator.key').exists(),
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
            if action not in ('start', 'resume', 'sync'):
                raise RuntimeError('Unknown updater action.')
            if not (STATE / 'operator.key').exists():
                raise RuntimeError('This computer needs administrator setup.')
            self.gate.set()
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
            self.save(phase='complete', message='Complete. Both Sheets and Oracle are verified.', error=None)
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
                if run['state'] == 'awaiting_ireps':
                    evidence_path = STATE / (run['run_id'] + '.json')
                    if evidence_path.exists():
                        run = request('/runs/' + run['run_id'] + '/evidence', json.loads(evidence_path.read_text()))
                    else:
                        raise RuntimeError('The interrupted scan has no complete evidence yet. Choose Check for new payments to restart safely.')
                if run['state'] in ('preview_ready', 'needs_review', 'paused'):
                    request('/runs/' + run['run_id'] + '/apply', {})
                    run = request('/runs/' + run['run_id'])
                self.monitor(run)
                return
            if action == 'sync':
                self.monitor(request('/sync-sheets', {}))
                return
            # Never silently replace an unfinished server write.
            for old in request('/runs'):
                if old['state'] == 'applying':
                    self.save(run=old)
                    self.monitor(old)
                    return
            run = request('/runs', {})
            self.save(run=run, start=run['connector']['start'], end=run['connector']['end'])
            cfg = run['connector']
            with sync_playwright() as pw:
                browser = app.browser(pw, {}, self.log)
                reader = EvidenceReader(browser.contexts[0], self.log, self.checkpoint)
                try:
                    self.save(phase='login', message='Sign in to IREPS in the updater Chrome window using your digital token. This page continues automatically.')
                    reader.page.bring_to_front()
                    reader.login()
                    self.save(phase='collecting')
                    categories = cfg['categories']
                    statuses = reader.contracts(categories, '01/01/2020', cfg['end'])
                    failures = reader.failures(categories)
                    records = reader.payments(categories, cfg['start'], cfg['end'],
                        existing=set(cfg['existing_invoices']), known_due=collector_due_dates(cfg['known_due']))
                    pdfs = {}
                    folder = STATE / ('Invoices-' + run['run_id'])
                    folder.mkdir(exist_ok=True)
                    for record in records:
                        self.checkpoint()
                        self.log('Verifying invoice ' + record['invoice'])
                        pdfs[record['invoice']] = base64.b64encode(reader.download(record, folder / (record['invoice'] + '.pdf'))).decode()
                    wanted = {key(r['contract']) for r in records}
                    for contract, due in cfg['known_due'].items():
                        if day(due) in reader.confirmed_paid_due.get(key(contract), set()):
                            wanted.add(key(contract))
                    terms = {}
                    for contract in sorted(wanted):
                        self.checkpoint()
                        if contract not in statuses:
                            raise RuntimeError('Paid contract is absent from the official contract list: ' + contract)
                        self.log('Checking official unpaid schedule: ' + statuses[contract]['contract'])
                        terms[contract] = reader.terms({**statuses[contract], 'asof': cfg['end']}, raw=True)
                    evidence = dict(run_id=run['run_id'], start=cfg['start'], end=cfg['end'], completed_categories=categories,
                        contracts=list(statuses.values()), payments=list(reader.observed.values()), failures=failures,
                        terms=terms, pdfs=pdfs, warnings=reader.warnings)
                    (STATE / (run['run_id'] + '.json')).write_text(json.dumps(evidence), encoding='utf-8')
                finally:
                    reader.page.close()
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

    def snapshot(self):
        with self.lock:
            return {**self.state, 'busy': bool(self.thread and self.thread.is_alive())}

    def save(self, **changes):
        with self.lock:
            self.state.update(changes)
            write_state(self.path, self.state)

    def start(self, force=False):
        with self.lock:
            if self.thread and self.thread.is_alive():
                if force:
                    raise RuntimeError('Workbook sync is already running.')
                return
            if not (STATE / 'operator.key').is_file():
                if force:
                    raise RuntimeError('This computer needs administrator setup.')
                return
            self.thread = threading.Thread(target=self.work, args=(force,), daemon=True)
            self.thread.start()

    def work(self, force):
        from rp.workbooks import WorkbookSelection
        try:
            self.save(phase='checking', message='Checking selected local workbooks.', error=None)
            selection = WorkbookSelection(deskflow.userdir / 'workbooks.json')
            names = {'parcel': 'parcels.xlsx', 'catering': 'catering.xlsx', 'commercial': 'others.xlsx'}
            data = {}
            for group, name in names.items():
                path = selection.target('D:/ANIL/UK', group)
                data[name] = path.read_bytes()
            digest = hashlib.sha256(b''.join(hashlib.sha256(data[name]).digest() for name in sorted(data))).hexdigest()
            if not force and digest == self.snapshot().get('digest'):
                self.save(phase='complete', message='Local workbooks are already synced.', error=None)
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
            self.save(phase='complete', message='Local workbook history is up to date.',
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
                with controller.lock, deskflow.lock:
                    if software_update_running():
                        raise RuntimeError('The desktop companion is updating. Wait for it to finish.')
                    return self.respond(200, deskflow.command(self.path.rsplit('/',1)[-1], data))
            except (ValueError, KeyError, TypeError, RuntimeError) as exc:
                return self.respond(400, {'error': str(exc)})
        if self.path not in ('/start', '/resume', '/pause', '/sync'):
            return self.respond(404, {'error': 'Not found.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 256 or json.loads(self.rfile.read(length)) != {}:
                return self.respond(400, {'error': 'Expected an empty JSON object.'})
            controller.command(self.path[1:])
            self.respond(202, controller.snapshot())
        except (ValueError, RuntimeError) as exc:
            self.respond(409, {'error': str(exc)})


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
                        archive_sync.start(force=True)
                    elif command.get('action') in ('collect', 'history'):
                        with controller.lock, deskflow.lock:
                            if software_update_running():
                                raise RuntimeError('The desktop companion is updating. Wait for it to finish.')
                            deskflow.command(command['action'], {})
                except (ValueError, RuntimeError) as exc:
                    deskflow.state.update(phase='error', error=str(exc), message='Deskflow command could not start.')
        except Exception:
            pass  # Retain local collection and retry when the API is available.
        time.sleep(4)


def serve():
    threading.Thread(target=deskflow_relay_loop, daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()


if __name__ == '__main__':
    serve()
