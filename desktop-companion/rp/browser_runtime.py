"""Use Playwright's shipped Node driver in source and standalone installations."""
from pathlib import Path
import playwright
import atexit,json,subprocess,threading

_proxy=None
_proxy_lock=threading.Lock()


def browser_reader_runtime():
    driver = Path(playwright.__file__).resolve().parent / 'driver'
    node = driver / 'node.exe'
    package = driver / 'package'
    if not node.is_file() or not (package / 'package.json').is_file():
        raise RuntimeError('The browser driver is missing. Reinstall SBC NAV Updater.')
    return node, package

def _stop_proxy():
    global _proxy
    if _proxy and _proxy[1].poll() is None:
        _proxy[1].terminate()
    _proxy=None

atexit.register(_stop_proxy)

def ireps_browser_endpoint(port):
    """Attach the reader only to IREPS; unrelated frozen tabs cannot stall it."""
    global _proxy
    port=int(port)
    if not 1<=port<=65535:raise ValueError('Invalid dedicated browser port.')
    with _proxy_lock:
        if _proxy and _proxy[0]==port and _proxy[1].poll() is None:return _proxy[2]
        _stop_proxy()
        node,package=browser_reader_runtime()
        process=subprocess.Popen([str(node),str(Path(__file__).with_name('ireps_cdp.mjs')),str(port),str(package)],
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf8',
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        timer=threading.Timer(15,process.kill);timer.start()
        try:
            line=process.stdout.readline()
            proxy_port=int(json.loads(line)['port'])
            if not 1<=proxy_port<=65535 or process.poll() is not None:raise ValueError('Invalid reader endpoint.')
        except Exception as exc:
            if process.poll() is None:process.terminate()
            raise RuntimeError('The isolated IREPS browser connection could not start.') from exc
        finally:timer.cancel()
        endpoint=f'http://127.0.0.1:{proxy_port}'
        _proxy=(port,process,endpoint)
        return endpoint
