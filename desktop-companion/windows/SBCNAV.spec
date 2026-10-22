from pathlib import Path
import sys
import importlib.metadata
from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPECPATH).parent
sys.path[:0] = [str(root), str(root / 'engine')]
playwright_data, playwright_binaries, playwright_imports = collect_all('playwright')
datas = playwright_data + [(str(root / 'rp' / name), 'rp') for name in ('collect.mjs', 'reader.js')]
datas += [(str(root / 'engine' / 'config.json'), 'engine')]
datas += [(str(Path(SPECPATH) / 'QUICK START.html'), '.')]
for name in ('playwright', 'openpyxl', 'lxml', 'pypdf', 'psutil', 'greenlet', 'pyee'):
    distribution = importlib.metadata.distribution(name)
    for file in distribution.files or []:
        if ('license' in str(file).lower() or 'copying' in str(file).lower()) and '.dist-info/' in str(file):
            datas.append((str(distribution.locate_file(file)), 'licenses/' + name))
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if python_license.exists():
    datas.append((str(python_license), 'licenses/python'))
imports = playwright_imports + collect_submodules('rp') + [
    'server', 'deskflow', 'app', 'core', 'planner', 'sheets', 'ireps',
    'incremental', 'resume', 'checkpoint', 'state_store', 'tkinter', 'tkinter.ttk',
    'tkinter.filedialog', 'tkinter.messagebox', 'openpyxl', 'lxml.etree', 'pypdf', 'psutil']
a = Analysis([str(root / 'portable.py')], pathex=[str(root), str(root / 'engine')],
    binaries=playwright_binaries, datas=datas, hiddenimports=imports,
    excludes=['pytest', 'IPython', 'jupyter', 'notebook', 'matplotlib', 'numpy', 'pandas'],
    noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='SBCNAVUpdater',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='SBCNAVUpdater')
