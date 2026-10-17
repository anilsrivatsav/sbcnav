"""Windows desktop entry point. Authentication happens only in normal Chrome pages."""
import json, os, queue, re, socket, subprocess, sys, threading, time, traceback, urllib.request
from pathlib import Path
from datetime import datetime, timedelta, timezone
import tkinter as tk
from tkinter import ttk, messagebox
from core import day, invoice, key, cell, actual, entered, master_contract_key, latest_recorded_date
from planner import main_plan, compact
from sheets import export, workbook, grid, SheetUI, verify
from ireps import Ireps, HOME
from incremental import queries as incremental_queries
from resume import read_google, apply_plan, run_saved
from checkpoint import seven_day_failures, completed_range

BASE = Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
STATE = Path(os.environ.get('LOCALAPPDATA',str(BASE))) / 'IREPS Earnings Updater'
STATE.mkdir(parents=True,exist_ok=True)
INDIA = timezone(timedelta(hours=5,minutes=30))

def now():
    return datetime.now(INDIA)

def latest_preview(include_completed=False):
    root=STATE/'Runs'
    if not root.exists():return None
    for folder in sorted(root.iterdir(),reverse=True):
        if not folder.is_dir() or not all((folder/name).exists() for name in ('plan.json','report.json','evidence.json','Earnings before.xlsx','Master before.xlsx')):
            continue
        try:
            report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
            if include_completed or report.get('state')!='complete and verified':return folder
            return None
        except (ValueError,OSError):continue
    return None

def column(n):
    result = ''
    while n:
        n,a = divmod(n-1,26)
        result = chr(65+a)+result
    return result

def chrome_path():
    candidates = [Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Google/Chrome/Application/chrome.exe',
                  Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Google/Chrome/Application/chrome.exe',
                  Path(os.environ.get('LOCALAPPDATA',''))/'Google/Chrome/Application/chrome.exe']
    return next((str(p) for p in candidates if p.exists()),None)

def browser(pw, config, log):
    session_file = STATE/'browser.json'
    profile = STATE/'Chrome profile'
    if session_file.exists():
        port = json.loads(session_file.read_text())['port']
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version',timeout=2).close()
        except Exception:
            pass
        else:
            log('Connecting to the app Chrome window…')
            try:
                return pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}',timeout=15000)
            except Exception:
                log('The updater browser is not responding. Restarting its dedicated window; sign in again if requested.')
                restart_owned_chrome(profile)
    chrome = chrome_path()
    if not chrome:
        raise RuntimeError('Google Chrome is required. Install Chrome, then run the updater again.')
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        port = s.getsockname()[1]
    log('Opening a normal Chrome window dedicated to this app.')
    subprocess.Popen([chrome,f'--remote-debugging-port={port}', '--remote-debugging-address=127.0.0.1',
                      f'--user-data-dir={profile}','--no-first-run', HOME,
                      'https://accounts.google.com/'],
                     stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    session_file.write_text(json.dumps({'port':port}))
    for _ in range(60):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version',timeout=1).close()
        except Exception:
            time.sleep(1)
            continue
        try:
            return pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}',timeout=30000)
        except Exception as exc:
            raise RuntimeError('The new updater Chrome window did not respond. Close its tabs and try again. No spreadsheet data was changed.') from exc
    raise RuntimeError('Chrome connection failed. Close only the app Chrome window and try again.')

def restart_owned_chrome(profile):
    """Recover only Chrome processes rooted in this application's profile."""
    import psutil
    expected = str(profile.resolve()).casefold()
    owned = []
    for proc in psutil.process_iter(['name','cmdline']):
        try:
            if (proc.info['name'] or '').lower() != 'chrome.exe':
                continue
            args = proc.info['cmdline'] or []
            if any(a.startswith('--type=') for a in args):
                continue
            profiles = [a.split('=',1)[1] for a in args if a.startswith('--user-data-dir=')]
            if len(profiles) == 1 and str(Path(profiles[0]).resolve()).casefold() == expected:
                owned.extend([c for c in proc.children(recursive=True) if c.name().lower()=='chrome.exe'])
                owned.append(proc)
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            continue
    for proc in owned:
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(owned,timeout=5)
    if alive:
        raise RuntimeError('The updater Chrome window could not be restarted. Close that window manually and retry.')

def fingerprint(g):
    return json.dumps([[c.get('userEnteredValue',{}) for c in r] for r in g],sort_keys=True)

def write_patches(ui, patches, cancel):
    for r,c,rows in compact(patches):
        if cancel():
            raise RuntimeError('Stopped between writes. Review the report; a rerun will skip recorded invoice numbers.')
        end = r+len(rows)-1
        a1 = f'{column(c)}{r}:{column(c+len(rows[0])-1)}{end}'
        ui.log('Writing '+ui.title+' '+a1)
        ui.paste(a1,rows)
        ui.saved()

def run(config,start,end,preview,log,cancel,authenticate,resume_folder=None):
    import msvcrt
    with (STATE/'run.lock').open('a+b') as guard:
        if guard.tell() == 0:
            guard.write(b'0'); guard.flush()
        guard.seek(0)
        try:
            msvcrt.locking(guard.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            raise RuntimeError('An update or preview is already running. Wait for it to finish before starting another.')
        try:
            if resume_folder is not None:
                return run_saved(config,resume_folder,log,cancel,authenticate,browser,now,write_patches)
            return _run(config,start,end,preview,log,cancel,authenticate)
        finally:
            guard.seek(0)
            msvcrt.locking(guard.fileno(),msvcrt.LK_UNLCK,1)

def _run(config,start,end,preview,log,cancel,authenticate):
    from playwright.sync_api import sync_playwright
    folder = STATE/'Runs'/now().strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True,exist_ok=False)
    report = {'start':start,'end':end,'preview':preview,'state':'collecting','phases':[]}
    report['targets']={k:config[k] for k in ('earnings_id','master_id','earnings_tab','master_tab','status_tab')}
    def journal():
        (folder/'report.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    journal()
    try:
        with sync_playwright() as pw:
            b = browser(pw,config,log)
            context = b.contexts[0]
            log('Sign in to Google and IREPS in the app Chrome window. Use your digital token / signer normally, then click Continue after login in this app.')
            authenticate()
            reader = Ireps(context,log,cancel)
            reader.login()
            log('AUTH|IREPS signed in')
            sheets=read_google(context,config,log,authenticate)
            data_e,data_m=sheets['earnings'],sheets['master']
            (folder/'Earnings before.xlsx').write_bytes(data_e)
            (folder/'Master before.xlsx').write_bytes(data_m)
            ef,ev = workbook(data_e)
            mf,mv = workbook(data_m)
            earnings = grid(ef,ev,config['earnings_tab'],28)
            master = grid(mf,mv,config['master_tab'],37)
            latest = latest_recorded_date(earnings)
            end_date = now().date()
            if latest > end_date:
                raise RuntimeError('The latest recorded earnings date is in the future. Check column C before updating.')
            # Include the last recorded day so late arrivals on that day are collected.
            # Invoice identity in the planner prevents existing payments being duplicated.
            start, end = latest.strftime('%d/%m/%Y'), end_date.strftime('%d/%m/%Y')
            report.update(start=start, end=end, last_recorded=start)
            journal()
            log('DATE_RANGE|'+start+'|'+end)
            log('Latest recorded earnings: '+start+'. Checking through '+end+' (existing invoices are skipped).')
            old_status_lengths = {config['earnings_id']:ef[config['status_tab']].max_row if config['status_tab'] in ef.sheetnames else 0,
                                  config['master_id']:mf[config['status_tab']].max_row if config['status_tab'] in mf.sheetnames else 0}
            categories = config['categories']
            failures = reader.failures(categories)
            asof = now().strftime('%d/%m/%Y')
            statuses = reader.contracts(categories,config['contract_scan_from'],asof)
            previous_failures=[]
            checkpoint=latest_preview(include_completed=True)
            if checkpoint:
                previous_failures=json.loads((checkpoint/'evidence.json').read_text(encoding='utf-8')).get('failures',[])
            scan_queries=None
            if config.get('scan_mode','incremental')=='incremental':
                scan_queries=incremental_queries(master,statuses,failures,previous_failures,categories)
                log('Incremental search: active installment schedules, known failed dues, and untracked active contracts. Historical paid schedules will not be searched.')
                report['scan_mode']='incremental scheduled dues'
            else:
                report['scan_mode']='full reconciliation'
            existing={str(actual(r[19])).strip() for r in earnings if actual(r[19])}
            known_due={master_contract_key(r):day(actual(r[17])) if actual(r[17]) else None for r in master[1:] if master_contract_key(r)}
            records = reader.payments(categories,start,end,queries=scan_queries,existing=existing,known_due=known_due)
            payments = []
            (folder/'Invoices').mkdir()
            for i,r in enumerate(records,1):
                log(f"Checking invoice {i}/{len(records)}: {r['invoice']}")
                payments.append(invoice(reader.download(r,folder/'Invoices'/(r['invoice']+'.pdf')),r))
            terms = {}
            for k in sorted({key(p['contract']) for p in payments}):
                if k not in statuses:
                    raise RuntimeError('Paid contract was not found in contract status scan. Expand the scan start date in config.json.')
                log('Reading official terms and unpaid schedule: '+statuses[k]['contract'])
                terms[k] = reader.terms({**statuses[k],'asof':asof})
                terms[k]['paid_dates']=sorted(reader.confirmed_paid_due.get(k,set()))
            report['source_warnings'] = reader.warnings
            (folder/'evidence.json').write_text(json.dumps({'payments':payments,'terms':terms,'statuses':statuses,'failures':failures},indent=2,default=str),encoding='utf-8')
            plan = main_plan(earnings,master,payments,terms,statuses,failures,asof)
            (folder/'plan.json').write_text(json.dumps(plan,indent=2,default=str),encoding='utf-8')
            report['summary'] = plan['summary']
            log('Plan: '+json.dumps(plan['summary'],ensure_ascii=False))
            if preview:
                report['state'] = 'preview complete - no spreadsheet writes'
                journal()
                reader.page.close()
                return folder,report
            apply_plan(context,config,folder,report,plan,{'earnings':earnings,'master':master},log,cancel,write_patches,journal,authenticate)
            reader.page.close()
            return folder,report
    except Exception as exc:
        report['state'] = 'stopped'
        report['error'] = str(exc)
        journal()
        log('Stopped: '+str(exc))
        log('Report folder: '+str(folder))
        raise

class App:
    def __init__(self,root):
        self.root,self.messages = root,queue.Queue()
        self.stop_event,self.auth_event = threading.Event(),threading.Event()
        self.running=False
        self.closing=False
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.title('IREPS • Earnings & Contracts — v2')
        root.geometry('1040x'+str(max(680,min(810,root.winfo_screenheight()-100))))
        root.minsize(900,680)
        root.configure(background='#eef2f7')
        style=ttk.Style(root)
        style.theme_use('clam')
        style.configure('TFrame',background='#eef2f7')
        style.configure('Card.TFrame',background='white')
        style.configure('TLabel',background='#eef2f7',foreground='#172b4d',font=('Segoe UI',11))
        style.configure('Card.TLabel',background='white',font=('Segoe UI',11))
        style.configure('Title.TLabel',background='#142b49',foreground='white',font=('Segoe UI',23,'bold'))
        style.configure('Subtitle.TLabel',background='#142b49',foreground='#c7dbed',font=('Segoe UI',11))
        style.configure('TButton',font=('Segoe UI',11),padding=(16,10))
        style.configure('Primary.TButton',background='#176bdb',foreground='white')
        style.map('Primary.TButton',background=[('disabled','#afc4df'),('active','#125bbd')])
        style.configure('TRadiobutton',background='white',font=('Segoe UI',11),padding=8)
        header=tk.Frame(root,bg='#142b49',padx=28,pady=22)
        header.pack(fill='x')
        ttk.Label(header,text='Earnings & Contract Updater',style='Title.TLabel').pack(anchor='w')
        ttk.Label(header,text='IREPS → Earnings Master + Master Contracts',style='Subtitle.TLabel').pack(anchor='w',pady=(8,0))
        frame=ttk.Frame(root,padding=(24,18))
        frame.pack(fill='both',expand=True)
        card=ttk.Frame(frame,style='Card.TFrame',padding=18)
        card.pack(fill='x')
        ttk.Label(card,text='1   Sign in     →     2   Read latest date     →     3   Review or update',style='Card.TLabel',font=('Segoe UI',12,'bold')).pack(anchor='w')
        ttk.Label(card,text='Chrome opens for your Google and IREPS login. Use your digital token in the browser.',style='Card.TLabel').pack(anchor='w',pady=(10,14))
        datebar=tk.Frame(card,bg='#f0f6ff',padx=14,pady=12)
        datebar.pack(fill='x')
        self.range_text=tk.StringVar(value='Automatic date range • Read from Earnings Master after login')
        ttk.Label(datebar,textvariable=self.range_text,background='#f0f6ff',foreground='#174678',font=('Segoe UI',12,'bold')).pack(anchor='w')
        ttk.Label(card,text='The last recorded day is checked again for late payments. Existing invoices are skipped.',style='Card.TLabel').pack(anchor='w',pady=(9,0))
        self.preview=tk.BooleanVar(value=True)
        modes=ttk.Frame(card,style='Card.TFrame')
        modes.pack(fill='x',pady=(12,0))
        ttk.Radiobutton(modes,text='Preview changes',variable=self.preview,value=True).pack(side='left')
        ttk.Radiobutton(modes,text='Update both sheets',variable=self.preview,value=False).pack(side='left',padx=18)
        buttons=ttk.Frame(frame)
        buttons.pack(fill='x',pady=14)
        self.start_button=ttk.Button(buttons,text='Check new data',style='Primary.TButton',command=self.start_run)
        self.start_button.pack(side='left')
        self.continue_button=ttk.Button(buttons,text='Continue after sign-in',command=self.auth_event.set,state='disabled')
        self.continue_button.pack(side='left',padx=10)
        self.resume_button=ttk.Button(buttons,text='Apply / Resume preview',command=self.resume_saved,state='disabled')
        self.resume_button.pack(side='left',padx=(0,10))
        ttk.Button(buttons,text='Stop',command=self.stop_event.set).pack(side='left')
        ttk.Button(buttons,text='Reports',command=self.open_reports).pack(side='right')
        self.state_text=tk.StringVar(value='Ready • Preview mode selected')
        tk.Label(frame,textvariable=self.state_text,font=('Segoe UI',11,'bold'),bg='#eef2f7',fg='#172b4d',anchor='w').pack(fill='x',pady=(0,8))
        self.progress=ttk.Progressbar(frame,mode='indeterminate')
        self.progress.pack(fill='x',pady=(0,12))
        self.auth_text=tk.StringVar(value='IREPS: waiting for sign-in • Google Sheets: access not checked')
        self.auth_status={'IREPS':'not checked','Google Sheets':'not checked'}
        ttk.Label(frame,textvariable=self.auth_text,font=('Segoe UI',10)).pack(anchor='w',pady=(0,8))
        self.summary_text=tk.StringVar(value='No changes have been applied.')
        ttk.Label(frame,textvariable=self.summary_text,font=('Segoe UI',11,'bold'),wraplength=950).pack(anchor='w',pady=(0,8))
        self.full_scan=tk.BooleanVar(value=False)
        ttk.Checkbutton(frame,text='Full payment reconciliation (includes older closed contracts; slower)',variable=self.full_scan).pack(anchor='w',pady=(0,8))
        self.tabs=ttk.Notebook(frame)
        self.tabs.pack(fill='both',expand=True)
        results=ttk.Frame(self.tabs,padding=8)
        activity=ttk.Frame(self.tabs,padding=8)
        self.tabs.add(results,text='Preview / issues')
        failed=ttk.Frame(self.tabs,padding=8)
        self.tabs.add(failed,text='Payments beyond 7-day grace')
        self.failures_tab=failed
        ttk.Label(failed,text='Due date + 7 days, calculated from the IREPS-listed failures. Full source failures remain in Preview / issues.',wraplength=900,font=('Segoe UI',10)).pack(anchor='w',pady=(0,8))
        self.failure_tree=ttk.Treeview(failed,columns=('contract','contractor','amount','due','grace','days'),show='headings',height=7)
        for name,label,width in [('contract','Contract',280),('contractor','Contractor',180),('amount','Amount due',90),('due','Due date',100),('grace','Grace ends*',100),('days','Days past grace',90)]:
            self.failure_tree.heading(name,text=label);self.failure_tree.column(name,width=width,minwidth=60)
        failure_scroll=ttk.Scrollbar(failed,orient='vertical',command=self.failure_tree.yview)
        self.failure_tree.configure(yscrollcommand=failure_scroll.set)
        failure_scroll.pack(side='right',fill='y');self.failure_tree.pack(fill='both',expand=True)
        self.tabs.add(activity,text='Activity')
        self.tree=ttk.Treeview(results,columns=('contract','status','failure','amount','due'),show='headings',height=7)
        for name,label,width in [('contract','Contract',300),('status','Contract status',110),('failure','Payment status',240),('amount','Amount due',100),('due','Pay by',100)]:
            self.tree.heading(name,text=label);self.tree.column(name,width=width,minwidth=70)
        scrollbar=ttk.Scrollbar(results,orient='vertical',command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y');self.tree.pack(fill='both',expand=True)
        scroll=ttk.Scrollbar(activity)
        scroll.pack(side='right',fill='y')
        self.log_box=tk.Text(activity,wrap='word',height=12,font=('Consolas',10),state='disabled',bg='white',fg='#20344e',relief='flat',padx=10,pady=10,yscrollcommand=scroll.set)
        self.log_box.pack(fill='both',expand=True)
        scroll.configure(command=self.log_box.yview)
        ttk.Label(frame,text='Invoices • Next due dates • New contracts • Failed payments • Contract status',font=('Segoe UI',10)).pack(anchor='w',pady=(12,0))
        self.saved_folder=None
        saved=latest_preview()
        if not saved:saved=latest_preview(include_completed=True)
        if saved:self.load_preview(saved)
        self.log('Check new data prepares changes. Apply / Resume uses your saved preview without collecting IREPS again.')
        root.after(100,self.poll)

    def open_reports(self):
        (STATE/'Runs').mkdir(parents=True,exist_ok=True)
        os.startfile(STATE/'Runs')

    def load_preview(self,folder):
        try:
            plan=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
            report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
        except (ValueError,OSError):return
        self.saved_folder=folder
        self.resume_button.configure(state='normal')
        summary=plan['summary']
        self.summary_text.set(f"Saved preview: {summary['new_invoices']} new invoices | {summary['new_contracts']} new contracts | {summary['failed_payments']} failures | {summary['not_running']} source contracts not running. Not applied.")
        if report.get('write_started'):
            self.summary_text.set('Apply was paused. Some changes may already be present; Resume verifies and continues from the saved plan.')
        self.range_text.set('Saved preview: '+str(report.get('start',''))+' → '+str(report.get('end','')))
        self.tree.delete(*self.tree.get_children())
        for row in plan['status'][1:]:
            values=[entered(c) for c in row]
            if values[4]!='Running' or not values[5].startswith('No beyond-grace'):
                self.tree.insert('', 'end',values=(values[1],values[4],values[5],values[6],values[7]))
        self.failure_tree.delete(*self.failure_tree.get_children())
        seven_days=seven_day_failures(plan['status'],report.get('end') or now().strftime('%d/%m/%Y'))
        for values in seven_days:self.failure_tree.insert('','end',values=values)
        self.tabs.select(1 if seven_days else 0)
        if report.get('state')=='complete and verified':
            self.saved_folder=None
            self.resume_button.configure(state='disabled')
            self.summary_text.set(f"Verified update: {summary['new_invoices']} invoices | {summary['new_contracts']} contracts | {summary['failed_payments']} source failures. Both workbooks verified.")
            self.range_text.set(completed_range(report))
            self.state_text.set('Complete • Both workbooks updated and verified')

    def resume_saved(self):
        if self.saved_folder:self.start_run(self.saved_folder)

    def close(self):
        if self.running:
            self.closing=True
            self.stop_event.set()
            self.state_text.set('Stopping safely • Waiting for the current operation to finish')
        else:
            self.root.destroy()

    def log(self,text):
        self.messages.put(('log',text))

    def authenticate(self):
        self.auth_event.clear()
        self.messages.put(('auth',None))
        while not self.auth_event.wait(0.5):
            if self.stop_event.is_set():
                raise RuntimeError('Cancelled during sign-in.')
        self.messages.put(('auth_done',None))

    def start_run(self,resume_folder=None):
        try:
            config=json.loads((BASE/'config.json').read_text(encoding='utf-8'))
            config['scan_mode']='full' if self.full_scan.get() else 'incremental'
        except Exception as e:
            messagebox.showerror('Check settings',str(e)); return
        self.stop_event.clear(); self.auth_event.clear()
        self.running=True
        self.start_button.configure(state='disabled')
        self.resume_button.configure(state='disabled')
        self.tabs.select(2)
        self.state_text.set('Opening browser • Sign in, then press Continue')
        self.progress.start(12)
        preview=self.preview.get()
        def worker():
            try:
                result=run(config,None,None,preview,self.log,self.stop_event.is_set,self.authenticate,resume_folder)
                self.messages.put(('done',result))
            except Exception as e:
                self.messages.put(('error',str(e)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        while not self.messages.empty():
            kind,value=self.messages.get()
            if kind=='log':
                if value.startswith('AUTH|'):
                    auth=value.split('|',1)[1]
                    name='IREPS' if auth.startswith('IREPS') else 'Google Sheets'
                    self.auth_status[name]=auth.replace(name,'').strip()
                    self.auth_text.set('IREPS: '+self.auth_status['IREPS']+' • Google Sheets: '+self.auth_status['Google Sheets'])
                    continue
                if value.startswith('DATE_RANGE|'):
                    _,start,end=value.split('|')
                    self.range_text.set('Last recorded: '+start+'     →     Check through: '+end)
                    continue
                self.log_box.configure(state='normal'); self.log_box.insert('end',now().strftime('%H:%M:%S')+' '+value+'\n'); self.log_box.see('end'); self.log_box.configure(state='disabled')
            elif kind=='auth':
                self.continue_button.configure(state='normal')
            elif kind=='auth_done':
                self.state_text.set('Reading sheets and checking IREPS records…')
                self.continue_button.configure(state='disabled')
            elif kind in ('done','error'):
                self.running=False
                if self.closing:
                    self.root.destroy()
                    return
                self.progress.stop()
                self.state_text.set('Preview ready / update complete' if kind=='done' else 'Paused • Saved preview is kept')
                self.start_button.configure(state='normal'); self.continue_button.configure(state='disabled')
                if kind=='done':
                    folder,report=value
                    self.log(report['state']+' — '+str(folder))
                    if report.get('state')=='complete and verified':
                        self.load_preview(folder)
                        self.saved_folder=None
                        self.resume_button.configure(state='disabled')
                        self.summary_text.set('Both workbooks updated and verified.')
                        self.state_text.set('Complete • Changes applied')
                    else:
                        self.load_preview(folder)
                        self.state_text.set('Preview ready • Click Apply / Resume to write these changes')
                else:
                    saved=latest_preview()
                    if saved:self.load_preview(saved)
                    else:self.state_text.set('Check stopped • No completed preview to apply; retry Check new data')
                    self.tabs.select(2)
                    self.log('PAUSED: '+value)
                    instruction='Your saved preview is kept. Use Apply / Resume after resolving the issue.' if saved else 'No completed preview was prepared. No spreadsheet writes occurred. Retry Check new data after resolving the issue.'
                    messagebox.showerror('Action needed',value+'\n\n'+instruction)
        self.root.after(100,self.poll)

if __name__=='__main__':
    if '--browser-check' in sys.argv:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b=pw.chromium.launch(executable_path=chrome_path(),headless=True)
            p=b.new_page();p.set_content('<p>Browser driver ready</p>')
            assert p.locator('p').inner_text()=='Browser driver ready'
            b.close()
        (STATE/'package-check.json').write_text(json.dumps({'time':now().isoformat(),'browser_driver':'passed','frozen':bool(getattr(sys,'frozen',False))}),encoding='utf-8')
    elif '--self-check' in sys.argv:
        # Creates no browser and writes no spreadsheet.
        root=tk.Tk(); root.withdraw(); app=App(root); root.update(); root.destroy()
        print('GUI and imports OK')
    else:
        root=tk.Tk(); App(root); root.mainloop()
