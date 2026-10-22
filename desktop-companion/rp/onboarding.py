"""Windows prerequisites and the final, read-only IREPS sign-in check."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request

COMPONENTS = {
    'chrome': ('Google Chrome', 'https://dl.google.com/chrome/install/googlechromestandaloneenterprise64.msi', 'Chrome.msi'),
    'signer': ('IREPS Signer 1.5.1', 'https://www.ireps.gov.in/ireps/pki/IREPSSigner151.msi', 'IREPSSigner151.msi'),
}
# Versioned MSI downloaded from the official IREPS home-page link on 22 Oct 2026.
SIGNER_SHA256 = '1ebd6bd9e64ef7396a65e600064e27b579ea25da83b46b657b54d49844fef8a9'
TOKEN_HELP = {'Watchdata / ProxKey': 'https://www.watchdata.com/', 'HyperPKI': 'https://www.hypersecu.com/'}


def installed_software():
    import winreg
    found = set()
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, r'Software\Microsoft\Windows\CurrentVersion\Uninstall', 0, winreg.KEY_READ | view) as parent:
                    for index in range(winreg.QueryInfoKey(parent)[0]):
                        try:
                            with winreg.OpenKey(parent, winreg.EnumKey(parent, index)) as child:
                                name = winreg.QueryValueEx(child, 'DisplayName')[0]
                                try:
                                    version = winreg.QueryValueEx(child, 'DisplayVersion')[0]
                                except OSError:
                                    version = ''
                                found.add((str(name), str(version)))
                        except OSError:
                            pass
            except OSError:
                pass
    return sorted(found)


def prerequisites():
    from app import chrome_path
    software = installed_software()
    signers = [f'{name} {version}'.strip() for name, version in software if name.lower().startswith('irepssigner')]
    tokens = [f'{name} {version}'.strip() for name, version in software if re.search(r'proxkey|hyperpki|epass|safenet|idprotect|watchdata', name, re.I)]
    return {'chrome': bool(chrome_path()), 'signer': bool(signers), 'signer_names': signers, 'token_names': tokens}


def verify_component(kind, path):
    if kind == 'signer':
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != SIGNER_SHA256:
            raise ValueError('The IREPS signer download has changed. Open the official IREPS site to install its current signer, then retry setup.')
        return
    powershell = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    # A PowerShell 7 parent can export incompatible module search paths to Windows PowerShell.
    env = {**os.environ, 'SBCNAV_COMPONENT_FILE': str(path), 'PSModulePath': str(powershell.parent / 'Modules')}
    command = '$ErrorActionPreference="Stop"; $s=Get-AuthenticodeSignature -LiteralPath $env:SBCNAV_COMPONENT_FILE; @{status=[string]$s.Status;publisher=$s.SignerCertificate.Subject}|ConvertTo-Json -Compress'
    process = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command', command],
        env=env, capture_output=True, text=True, timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        signature = json.loads(process.stdout)
    except ValueError:
        signature = {}
    if process.returncode or signature.get('status') != 'Valid' or not re.search(r'\bGoogle (LLC|Inc)', signature.get('publisher') or '', re.I):
        raise ValueError('The Chrome installer signature could not be verified. Install Chrome from google.com/chrome, then retry setup.')


def install_component(kind, folder, log, cancelled=lambda: False):
    if kind not in COMPONENTS:
        raise ValueError('Unknown setup component.')
    label, url, name = COMPONENTS[kind]
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    temporary = folder / (Path(name).stem + '.download' + Path(name).suffix)
    log('Downloading ' + label + ' from its official website…')
    with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as stream:
        count = 0
        while block := response.read(1024 * 1024):
            if cancelled():
                raise ValueError('Setup paused. Open setup again to continue.')
            count += len(block)
            if count > 350 * 1024 * 1024:
                raise ValueError('The component download is unexpectedly large. Setup stopped.')
            stream.write(block)
            log(f'Downloading {label}… {count // (1024 * 1024)} MB')
    verify_component(kind, temporary)
    os.replace(temporary, target)
    if cancelled():
        raise ValueError('Setup paused. Open setup again to continue.')
    log('Complete the Windows installation for ' + label + '. Approve the administrator prompt if Windows asks.')
    msiexec = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/msiexec.exe'
    result = subprocess.run([str(msiexec), '/i', str(target), '/norestart'], timeout=1200)
    if result.returncode not in (0, 3010):
        raise ValueError(label + ' installation did not finish. Retry setup after completing or cancelling the Windows installer.')
    if not prerequisites()[kind]:
        raise ValueError(label + ' is not detected yet. Restart Windows if its installer requested it, then reopen SBC NAV Setup.')


def check_ireps(log, cancelled=lambda: False):
    from playwright.sync_api import sync_playwright
    import app
    from ireps import Ireps
    with sync_playwright() as playwright:
        browser = app.browser(playwright, {}, log)
        reader = Ireps(browser.contexts[0], log, cancelled)
        try:
            reader.page.bring_to_front()
            log('Sign in to IREPS in the updater Chrome window with your digital token. This setup screen will continue automatically.')
            reader.login()
        finally:
            reader.page.close()


def provision(connection, connect, start, folder, log, cancelled=lambda: False):
    """Retry from installed prerequisites; never collect payments or write Sheets."""
    if cancelled():
        raise ValueError('Setup paused. Open setup again to continue.')
    log('Checking the office connection…')
    connect(connection)
    for kind in ('chrome', 'signer'):
        if not prerequisites()[kind]:
            install_component(kind, folder, log, cancelled)
    log('Starting and checking the desktop connection…')
    status = start()
    if not status.get('configured'):
        raise ValueError('The desktop connection is not configured. Retry setup.')
    if status.get('busy') or status.get('deskflow_busy'):
        raise ValueError('An update is running on this PC. Finish it before checking IREPS sign-in.')
    check_ireps(log, cancelled)
