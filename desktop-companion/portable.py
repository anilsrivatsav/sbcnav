"""Standalone Windows entry point; no system Python or Codex is required."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

VERSION = '2.1.0'
ORIGIN = 'https://sbcnav-38t2.vercel.app'
API = 'https://sbcnav.137-23-58-53.sslip.io/api/mcdo'
DASHBOARD = ORIGIN + '/?view=mcdo'
STATE = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'IREPS Earnings Updater' / 'Web companion'
ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
RESOURCE = Path(__file__).resolve().parent
sys.path.insert(0, str(RESOURCE / 'engine'))


def connection_token(path):
    """A connection file contains a credential, never executable code or endpoints."""
    path = Path(path)
    if path.stat().st_size > 16384:
        raise ValueError('This is not an SBC NAV connection file.')
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict) or data.get('format') != 'sbcnav-connection-v1':
        raise ValueError('Choose the SBC NAV Connection.sbcnav file supplied with setup.')
    token = data.get('operator_token')
    if not isinstance(token, str) or not 32 <= len(token) <= 512 or any(c.isspace() for c in token):
        raise ValueError('The connection file is invalid. Ask for a new connection file.')
    return token


def install_connection(path):
    token = connection_token(path)
    req = urllib.request.Request(API + '/session', headers={'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.load(response)
            if not isinstance(result.get('data'), dict):
                raise ValueError('SBC NAV returned an unexpected response. Try again later.')
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ValueError('This connection file is no longer accepted. Ask for a new one.') from None
        raise ValueError('SBC NAV is temporarily unavailable. Try again later.') from None
    except (urllib.error.URLError, TimeoutError):
        raise ValueError('Cannot reach SBC NAV. Check the internet connection and try again.') from None
    from state_store import write_state
    STATE.mkdir(parents=True, exist_ok=True)
    # Same-directory replacement preserves a previous working credential on failure.
    import tempfile
    fd, temporary = tempfile.mkstemp(prefix='connection-', suffix='.tmp', dir=STATE)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(token)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(8):
            try:
                os.replace(temporary, STATE / 'operator.key')
                break
            except PermissionError:
                if attempt == 7:
                    raise ValueError('Windows is holding the connection file. Close setup and try again.') from None
                time.sleep(.1 * (attempt + 1))
    finally:
        Path(temporary).unlink(missing_ok=True)
    write_state(STATE / 'connection.json', {'connected': True, 'version': VERSION})


def ready():
    try:
        request = urllib.request.Request('http://127.0.0.1:48722/status', headers={'Origin': ORIGIN})
        with urllib.request.urlopen(request, timeout=2) as response:
            value = json.load(response)
            return value if value.get('connected') is True else None
    except (OSError, ValueError):
        return None


def start_service():
    status = ready()
    if status:
        return status
    args = [sys.executable, '--serve'] if getattr(sys, 'frozen', False) else [sys.executable, str(Path(__file__)), '--serve']
    subprocess.Popen(args, cwd=ROOT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        time.sleep(.2)
        status = ready()
        if status:
            return status
    raise ValueError('The desktop connection did not start. Open SBC NAV Setup again to retry.')


def setup():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from app import chrome_path
    window = tk.Tk()
    window.title('SBC NAV · Set up this PC')
    window.geometry('660x560')
    window.minsize(640, 540)
    window.configure(bg='#edf2f7')
    style = ttk.Style(window)
    style.theme_use('clam')
    style.configure('TFrame', background='white')
    style.configure('TLabel', background='white', foreground='#142c49')
    style.configure('Primary.TButton', font=('Segoe UI', 11, 'bold'), padding=(18, 12), background='#1d64b5', foreground='white')
    style.map('Primary.TButton', background=[('disabled', '#8199b5'), ('active', '#174e8d')])
    header = tk.Frame(window, bg='#142c49', padx=28, pady=24)
    header.pack(fill='x')
    tk.Label(header, text='SBC NAV', font=('Segoe UI', 24, 'bold'), bg='#142c49', fg='white').pack(anchor='w')
    tk.Label(header, text='Connect this Windows PC once', font=('Segoe UI', 12), bg='#142c49', fg='#cbdcee').pack(anchor='w')
    body = ttk.Frame(window, padding=28)
    body.pack(fill='both', expand=True)
    text = tk.StringVar()
    chrome = chrome_path()
    pending = STATE / 'pending.sbcnav'
    candidate = pending if pending.is_file() else ROOT / 'SBC NAV Connection.sbcnav'
    selected = [candidate if candidate.is_file() else None]
    text.set('Your private connection file is ready. Click Connect this PC.' if selected[0] else
             'Choose the SBC NAV Connection.sbcnav file supplied with the installer.')
    ttk.Label(body, text='1  Connect to SBC NAV', font=('Segoe UI', 13, 'bold')).pack(anchor='w')
    ttk.Label(body, textvariable=text, wraplength=550, font=('Segoe UI', 11)).pack(anchor='w', pady=(10, 16))
    def choose():
        name = filedialog.askopenfilename(parent=window, title='Choose your connection file', filetypes=[('SBC NAV connection', '*.sbcnav')])
        if name:
            selected[0] = Path(name)
            text.set('Connection file selected. Click Connect this PC.')
    browse = ttk.Button(body, text='Choose connection file…', command=choose)
    browse.pack(anchor='w')
    ttk.Label(body, text='2  Sign in when you update', font=('Segoe UI', 13, 'bold')).pack(anchor='w', pady=(22, 8))
    ttk.Label(body, text='Use Google Chrome and your digital token to sign in to IREPS.\nInstall your token driver and signer software on this PC first.', font=('Segoe UI', 11), wraplength=550).pack(anchor='w')
    if not chrome:
        ttk.Button(body, text='Install Google Chrome', command=lambda: webbrowser.open('https://www.google.com/chrome/')).pack(anchor='w', pady=8)
    def completed(error=None):
        connect.configure(state='normal')
        browse.configure(state='normal')
        if error:
            text.set(error)
            return
        if selected[0] == pending:
            pending.unlink(missing_ok=True)
        window.destroy()
        webbrowser.open(DASHBOARD)
    def connect_now():
        if not selected[0]:
            choose()
            if not selected[0]:
                return
        if not chrome_path():
            messagebox.showinfo('Install Chrome first', 'Install Google Chrome, then click Connect this PC again.', parent=window)
            return
        connect.configure(state='disabled')
        browse.configure(state='disabled')
        text.set('Checking your connection…')
        def work():
            try:
                install_connection(selected[0])
                start_service()
                error = None
            except Exception as exc:
                error = str(exc) if isinstance(exc, ValueError) else 'Setup could not finish. Check your internet connection and try again.'
            window.after(0, lambda: completed(error))
        threading.Thread(target=work, daemon=True).start()
    connect = ttk.Button(body, text='Connect this PC', style='Primary.TButton', command=connect_now)
    connect.pack(anchor='w', pady=(24, 0))
    window.mainloop()


def diagnostics(output):
    """Exercise the frozen app with a clean LOCALAPPDATA and no external Python/Node."""
    import platform
    import tempfile
    from http.server import ThreadingHTTPServer
    import server
    from playwright.sync_api import sync_playwright
    from rp.browser_runtime import browser_reader_runtime
    from rp.export_review import export_review
    report = {'version': VERSION, 'frozen': bool(getattr(sys, 'frozen', False)), 'python': platform.python_version()}
    report['configured'] = (STATE / 'operator.key').is_file()
    node, module = browser_reader_runtime()
    probe = subprocess.run([str(node), '-e', 'console.log(typeof require(process.argv[1]).chromium.connectOverCDP)', str(module)],
        capture_output=True, text=True, timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assert probe.returncode == 0 and probe.stdout.strip() == 'function', probe.stderr
    report['packaged_node_driver'] = True
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=server.app.chrome_path(), headless=True)
        page = browser.new_page()
        page.goto('data:text/html,<title>SBC NAV test</title><p id="ok">Ready</p>')
        assert page.locator('#ok').inner_text() == 'Ready'
        report['chrome_automation'] = True
        browser.close()
    server.PORT = 0
    http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    server.PORT = http.server_port
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        req = urllib.request.Request(f'http://127.0.0.1:{server.PORT}/status', headers={'Origin': ORIGIN})
        with urllib.request.urlopen(req, timeout=5) as response:
            assert json.load(response)['connected']
        report['local_web_connection'] = True
    finally:
        http.shutdown()
        http.server_close()
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'review.xlsx'
        values = ['2026-10-22', 'Parking', 'Test asset', '', 'year', 100, 'Test', 100, 1] + [''] * 13
        export_review(path, [{'values': values, 'formula': '=+H{r}*I{r}', 'expected': '100'}])
        from openpyxl import load_workbook
        wb = load_workbook(path, data_only=True)
        assert wb.active['F2'].value == 100
        wb.close()
        report['excel_export'] = True
    from state_store import write_state, read_state
    target = STATE / 'diagnostic-state.json'
    write_state(target, {'checked': True})
    assert read_state(target)['checked']
    report['checkpoint_persistence'] = True
    Path(output).write_text(json.dumps(report, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--background', action='store_true')
    parser.add_argument('--setup', action='store_true')
    parser.add_argument('--diagnostics')
    parser.add_argument('--connect-file')
    args, _ = parser.parse_known_args()
    if args.diagnostics:
        diagnostics(args.diagnostics)
    elif args.connect_file:
        install_connection(args.connect_file)
    elif args.serve:
        if not ready():
            import server
            server.serve()
    elif args.setup or not (STATE / 'operator.key').is_file():
        if not args.background:
            setup()
    else:
        start_service()
        if not args.background:
            webbrowser.open(DASHBOARD)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if '--connect-file' in sys.argv:
            sys.exit(1)
        if '--diagnostics' in sys.argv:
            import traceback
            path = Path(sys.argv[sys.argv.index('--diagnostics') + 1])
            path.write_text(json.dumps({'error': str(exc), 'traceback': traceback.format_exc()}, indent=2), encoding='utf-8')
            sys.exit(1)
        if '--background' not in sys.argv and '--serve' not in sys.argv:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror('SBC NAV needs attention', str(exc), parent=root)
            root.destroy()
