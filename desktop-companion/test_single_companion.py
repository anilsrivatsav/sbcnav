import ast,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler

class SingleInstanceTest(unittest.TestCase):
    def test_second_instance_cannot_bind_the_same_endpoint(self):
        source=ast.parse(Path(__file__).with_name('server.py').read_text(encoding='utf8'))
        node=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='SingleCompanionServer')
        namespace={'ThreadingHTTPServer':ThreadingHTTPServer}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'single-server','exec'),namespace)
        cls=namespace['SingleCompanionServer']
        first=cls(('127.0.0.1',0),BaseHTTPRequestHandler)
        try:
            with self.assertRaises(OSError):cls(first.server_address,BaseHTTPRequestHandler)
        finally:first.server_close()

if __name__=='__main__':unittest.main()
