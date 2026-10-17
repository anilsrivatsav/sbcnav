"""Start the local controller once; optionally open the web dashboard."""
import pathlib
import subprocess
import sys
import urllib.request
import webbrowser

folder = pathlib.Path(__file__).resolve().parent
try:
    req = urllib.request.Request('http://127.0.0.1:48721/status', headers={'Origin': 'https://sbcnav-38t2.vercel.app'})
    with urllib.request.urlopen(req, timeout=2) as response:
        response.read()
except Exception:
    subprocess.Popen([sys.executable, str(folder / 'server.py')], cwd=folder,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
if '--background' not in sys.argv:
    webbrowser.open('https://sbcnav-38t2.vercel.app/?view=mcdo')
