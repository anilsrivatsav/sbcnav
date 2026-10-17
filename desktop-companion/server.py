"""Loopback-only web controller for the proven Windows IREPS collector.

The operator credential never enters browser JavaScript. Only the configured
dashboard origin can invoke commands; no arbitrary URLs, files or scripts are accepted.
"""
import base64
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / 'engine'))
import app
from core import day, key
from ireps import Ireps, HOME
from playwright.sync_api import sync_playwright

PORT = 48722
ORIGIN = 'https://sbcnav-38t2.vercel.app'
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
            self.state.update(json.loads((STATE / 'state.json').read_text()))
            if self.state['phase'] not in ('ready', 'complete', 'error'):
                self.state.update(phase='interrupted', message='The computer restarted. Resume checks saved progress before continuing.')
        except (OSError, ValueError):
            pass

    def save(self, **values):
        with self.lock:
            self.state.update(values)
            temp = STATE / 'state.tmp'
            temp.write_text(json.dumps(self.state), encoding='utf-8')
            temp.replace(STATE / 'state.json')

    def snapshot(self):
        with self.lock:
            return {**self.state, 'busy': bool(self.thread and self.thread.is_alive()),
                    'connected': True, 'version': '2.0.1', 'configured': (STATE / 'operator.key').exists()}

    def log(self, message):
        message = str(message).split('\nCall log:', 1)[0]
        with self.lock:
            self.save(message=message, logs=(self.state['logs'] + [app.now().strftime('%H:%M:%S') + ' ' + message])[-100:])

    def checkpoint(self):
        self.gate.wait()
        return False

    def command(self, action):
        with self.lock:
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


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def permitted(self):
        return self.headers.get('Host') == f'127.0.0.1:{PORT}' and self.headers.get('Origin') == ORIGIN

    def respond(self, status, value):
        if self.path.startswith('/deskflow/'):
            value=public_text(value)
        self.send_response(status)
        if self.permitted():
            self.send_header('Access-Control-Allow-Origin', ORIGIN)
            self.send_header('Vary', 'Origin')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
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
        if self.path == '/deskflow/progress':
            return self.respond(200, deskflow.progress())
        if self.path == '/deskflow/status':
            return self.respond(200, deskflow.snapshot())
        if self.path != '/status':
            return self.respond(404, {'error': 'Not found.'})
        self.respond(200, controller.snapshot())

    def do_POST(self):
        if not self.permitted() or self.headers.get('Content-Type') != 'application/json':
            return self.respond(403, {'error': 'Origin or content type not allowed.'})
        if self.path.startswith('/deskflow/'):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2_000_000: raise ValueError('Invalid request size.')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict): raise ValueError('Expected a JSON object.')
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


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
