"""Use the application's authenticated HTTPS gateway when direct Oracle access is blocked.

Cookies stay in memory. Financial POST requests are never replayed after a network
failure; the updater's existing run/readback checkpoints decide what to resume.
"""
import hashlib
import http.cookiejar
import json
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.request

ORIGIN = 'https://sbcnav-38t2.vercel.app'
GATEWAY = ORIGIN + '/api/mcdo'


class GatewayClient:
    def __init__(self, state):
        self.state = Path(state)
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.lock = threading.RLock()
        self.authenticated_key = None
        self.generation = 0

    def _call(self, path, body=None, token=None):
        headers = {'Origin': ORIGIN, 'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(GATEWAY + path,
            data=None if body is None else json.dumps(body).encode('utf-8'), headers=headers)
        safe_to_retry = body is None or (path == '/session' and token is not None)
        attempts = 3 if safe_to_retry else 1
        for attempt in range(attempts):
            try:
                with self.opener.open(req, timeout=120) as response:
                    result = json.load(response)
                break
            except urllib.error.HTTPError as exc:
                if exc.code not in (502, 503, 504) or attempt + 1 == attempts:
                    raise
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt + 1 == attempts:
                    raise
            time.sleep(attempt + 1)
        if not isinstance(result, dict) or 'data' not in result:
            raise RuntimeError('MCDO returned an unexpected response. Saved progress is retained.')
        return result['data']

    def _login(self, token, fingerprint):
        self.cookies.clear()
        self.authenticated_key = None
        self._call('/session', {}, token)
        if not any(c.name == 'sbcnav_mcdo_session' for c in self.cookies):
            raise RuntimeError('The MCDO gateway did not establish a session. Retry the update.')
        self.authenticated_key = fingerprint
        self.generation += 1

    @staticmethod
    def _http_error(exc):
        try:
            message = json.load(exc).get('detail', 'MCDO request failed.')
        except (ValueError, OSError):
            message = 'MCDO request failed (HTTP ' + str(exc.code) + ').'
        return RuntimeError(str(message)[:1800])

    def request(self, path, body=None):
        if not isinstance(path, str) or not re.fullmatch(r'/[A-Za-z0-9/-]+', path) or '//' in path:
            raise ValueError('Invalid MCDO route.')
        token = (self.state / 'operator.key').read_text(encoding='utf-8-sig').strip()
        if not 32 <= len(token) <= 512 or any(c.isspace() for c in token):
            raise RuntimeError('The saved office connection is invalid. Reconnect this PC through setup.')
        fingerprint = hashlib.sha256(token.encode()).digest()
        try:
            with self.lock:
                if self.authenticated_key != fingerprint:
                    self._login(token, fingerprint)
                generation = self.generation
            try:
                return self._call(path, body)
            except urllib.error.HTTPError as exc:
                if exc.code != 401:
                    raise
                # An authentication rejection occurs before any write is accepted.
                with self.lock:
                    if self.generation == generation:
                        self._login(token, fingerprint)
                return self._call(path, body)
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise RuntimeError('The MCDO gateway connection was interrupted. Saved progress is retained; resume checks the server before retrying a write. ' + str(exc).split('Call log:')[0][:300]) from None
