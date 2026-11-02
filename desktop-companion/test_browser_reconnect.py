import ast
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


class ReconnectTests(unittest.TestCase):
    def run_connection(self, failures):
        tree=ast.parse((Path(__file__).parent/'engine/app.py').read_text(encoding='utf-8'))
        function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='browser')
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder);(state/'browser.json').write_text(json.dumps({'port':12345}))
            connect=Mock(side_effect=failures)
            restart=Mock();popen=Mock()
            scope={'STATE':state,'json':json,'urllib':SimpleNamespace(request=SimpleNamespace(urlopen=Mock(return_value=Mock()))),
                   'restart_owned_chrome':restart,'subprocess':SimpleNamespace(Popen=popen)}
            exec(compile(ast.Module(body=[function],type_ignores=[]),'browser-reconnect-fixture','exec'),scope)
            pw=SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=connect))
            try: result=scope['browser'](pw,{},Mock())
            finally:
                restart.assert_not_called();popen.assert_not_called()
            return result,connect

    def test_retry_keeps_the_open_browser(self):
        marker=object();result,connect=self.run_connection([RuntimeError('temporary'),marker])
        self.assertIs(result,marker)
        self.assertEqual(connect.call_count,2)

    def test_repeated_attach_failure_does_not_close_the_user_session(self):
        with self.assertRaisesRegex(RuntimeError,'window and session were retained'):
            self.run_connection([RuntimeError('temporary'),RuntimeError('still unavailable')])

if __name__=='__main__':unittest.main()
