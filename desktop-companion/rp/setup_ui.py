"""One-page onboarding, with retryable checks and a verified completion screen."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog
import webbrowser
from .onboarding import prerequisites, provision, TOKEN_HELP


def show(state, root, version, dashboard, install_connection, start_service, validate_existing):
    window = tk.Tk()
    window.title('SBC NAV · Set up this PC')
    window.geometry('720x720')
    window.minsize(680, 680)
    window.configure(bg='#edf2f7')
    style = ttk.Style(window)
    style.theme_use('clam')
    style.configure('TFrame', background='white')
    style.configure('TLabel', background='white', foreground='#142c49')
    style.configure('Primary.TButton', font=('Segoe UI', 11, 'bold'), padding=(18, 12), background='#1d64b5', foreground='white')
    style.map('Primary.TButton', background=[('disabled', '#8199b5'), ('active', '#174e8d')])
    header = tk.Frame(window, bg='#142c49', padx=28, pady=24)
    header.pack(fill='x')
    tk.Label(header, text='Set up SBC NAV on this PC', font=('Segoe UI', 22, 'bold'), bg='#142c49', fg='white').pack(anchor='w')
    tk.Label(header, text='One setup · then update from MCDO', font=('Segoe UI', 12), bg='#142c49', fg='#cbdcee').pack(anchor='w')
    footer = ttk.Frame(window, padding=(26, 16))
    footer.pack(side='bottom', fill='x')
    viewport = ttk.Frame(window)
    viewport.pack(fill='both', expand=True)
    canvas = tk.Canvas(viewport, bg='white', highlightthickness=0)
    scrollbar = ttk.Scrollbar(viewport, orient='vertical', command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    body = ttk.Frame(canvas, padding=26)
    body_id = canvas.create_window((0, 0), window=body, anchor='nw')
    body.bind('<Configure>', lambda _: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda event: canvas.itemconfigure(body_id, width=event.width))
    window.bind('<MouseWheel>', lambda event: canvas.yview_scroll(int(-event.delta / 120), 'units'))
    ttk.Label(body, text='Setup checks the office connection, installs missing Chrome and IREPS Signer, and verifies your token sign-in.', wraplength=650, font=('Segoe UI', 11)).pack(anchor='w', pady=(0, 14))
    pending = state / 'pending.sbcnav'
    candidate = pending if pending.is_file() else root / 'SBC NAV Connection.sbcnav'
    selected = [candidate if candidate.is_file() else None]
    configured = (state / 'operator.key').is_file()
    values = {}
    for name, label in [('office', 'Office connection'), ('chrome', 'Google Chrome'), ('signer', 'IREPS Signer'), ('token', 'Digital token software'), ('login', 'IREPS sign-in')]:
        row = ttk.Frame(body)
        row.pack(fill='x', pady=5)
        ttk.Label(row, text=label, font=('Segoe UI', 11, 'bold'), width=23).pack(side='left', anchor='n')
        values[name] = tk.StringVar(value='Checking…')
        ttk.Label(row, textvariable=values[name], wraplength=400, font=('Segoe UI', 10)).pack(side='left', anchor='n')
    values['office'].set('Saved on this PC' if configured else 'Included in this installer' if selected[0] else 'Authorised office setup needed')
    values['login'].set('Sign in with your digital token when Chrome opens')
    def refresh_components():
        found = prerequisites()
        values['chrome'].set('Installed' if found['chrome'] else 'Setup will install Chrome from Google')
        values['signer'].set('Installed' if found['signer'] else 'Setup will install the official IREPS Signer')
        values['token'].set(', '.join(found['token_names']) if found['token_names'] else 'Plug in your token. Install its vendor driver if sign-in asks for it.')
    refresh_components()
    events = queue.Queue()
    cancelled = threading.Event()
    running = [False]
    complete = [False]
    message = tk.StringVar(value='Ready. Windows may ask you to approve missing software installations.')
    ttk.Label(footer, textvariable=message, wraplength=650, font=('Segoe UI', 11)).pack(anchor='w', pady=(0, 12))
    controls = ttk.Frame(footer)
    controls.pack(fill='x')
    def primary_action():
        if complete[0]:
            webbrowser.open(dashboard)
            window.destroy()
            return
        if running[0]:
            return
        if not selected[0] and not (state / 'operator.key').is_file():
            message.set('Use the ready-to-use office EXE from MCDO on an already connected PC. You can also choose an existing private connection file under Recovery options below.')
            return
        running[0] = True
        primary.configure(state='disabled')
        recovery.configure(state='disabled')
        def worker():
            try:
                def connect(path):
                    if path:
                        install_connection(path)
                    else:
                        validate_existing()
                    events.put(('office', 'Verified with SBC NAV'))
                provision(selected[0], connect, start_service, state / 'Downloads', lambda text: events.put(('message', text)), cancelled.is_set)
                from state_store import write_state
                write_state(state / 'setup-complete.json', {'complete': True, 'version': version, 'ireps_login_verified': True})
                if selected[0] == pending:
                    try:
                        pending.unlink(missing_ok=True)
                    except OSError:
                        pass  # The installed credential and completion record are already durable.
                events.put(('complete', None))
            except Exception as exc:
                error = str(exc).split('Call log:')[0][:700]
                events.put(('error', error))
        threading.Thread(target=worker, daemon=True).start()
    primary = ttk.Button(controls, text='Set up and check this PC', style='Primary.TButton', command=primary_action)
    primary.pack(side='left')
    def choose():
        name = filedialog.askopenfilename(parent=window, title='Choose your private office connection file', filetypes=[('SBC NAV connection', '*.sbcnav')])
        if name:
            selected[0] = Path(name)
            values['office'].set('Connection file selected')
            message.set('Click Set up and check this PC to continue.')
    recovery = ttk.Button(body, text='Recovery: choose an existing connection file…', command=choose)
    recovery.pack(anchor='w', pady=(18, 8))
    ttk.Label(body, text='Token driver help — choose the manufacturer printed on your token:', wraplength=650).pack(anchor='w', pady=(8, 4))
    links = ttk.Frame(body)
    links.pack(anchor='w')
    for label, url in TOKEN_HELP.items():
        ttk.Button(links, text=label, command=lambda address=url: webbrowser.open(address)).pack(side='left', padx=(0, 8))
    ttk.Button(links, text='Official IREPS help', command=lambda: webbrowser.open('https://www.ireps.gov.in/')).pack(side='left')
    ttk.Label(body, text='Keep the office installer private. Setup does not collect payments or change Sheets. Your PIN and IREPS credentials are entered only in the normal sign-in screens.', wraplength=650, font=('Segoe UI', 9)).pack(anchor='w', pady=(16, 0))
    def drain():
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == 'message':
                    message.set(value)
                elif kind == 'office':
                    values['office'].set(value)
                elif kind == 'complete':
                    running[0] = False
                    complete[0] = True
                    refresh_components()
                    values['login'].set('Verified — IREPS Payments access confirmed')
                    message.set('This PC is ready. Open MCDO and choose Check for new payments whenever you want to update.')
                    primary.configure(state='normal', text='Open MCDO — ready to use')
                elif kind == 'error':
                    running[0] = False
                    refresh_components()
                    message.set(value + ' Your completed setup steps are kept. Fix the issue and choose Retry setup.')
                    primary.configure(state='normal', text='Retry setup')
                    recovery.configure(state='normal')
        except queue.Empty:
            pass
        window.after(100, drain)
    def close():
        cancelled.set()
        window.destroy()
    window.protocol('WM_DELETE_WINDOW', close)
    window.after(100, drain)
    window.mainloop()
