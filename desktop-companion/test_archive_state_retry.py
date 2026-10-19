import ast
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch


class ArchiveStateRetryTests(unittest.TestCase):
    def sync(self, folder):
        # Load the real state writer without starting the desktop controller.
        tree=ast.parse(Path(__file__).with_name('server.py').read_text(encoding='utf-8'))
        cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='WorkbookArchiveSync')
        scope={'json':json,'time':time}
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'server.py','exec'),scope)
        instance=object.__new__(scope['WorkbookArchiveSync'])
        instance.path=Path(folder)/'workbook-sync.json';instance.state={};instance.lock=threading.Lock()
        return instance

    def test_transient_windows_lock_is_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            sync=self.sync(folder);original=Path.replace;attempts=[]
            def replace(path,target):
                attempts.append(1)
                if len(attempts)==1:raise PermissionError('sharing violation')
                return original(path,target)
            with patch.object(Path,'replace',replace),patch.object(time,'sleep'):
                sync.save(phase='complete')
            self.assertEqual(len(attempts),2)
            self.assertEqual(json.loads(sync.path.read_text())['phase'],'complete')

    def test_permanent_failure_is_reported_without_erasing_old_state(self):
        with tempfile.TemporaryDirectory() as folder:
            sync=self.sync(folder);sync.path.write_text('{"phase":"old"}')
            with patch.object(Path,'replace',side_effect=PermissionError('denied')) as replace,patch.object(time,'sleep'):
                with self.assertRaises(PermissionError):sync.save(phase='complete')
            self.assertEqual(replace.call_count,10)
            self.assertEqual(json.loads(sync.path.read_text())['phase'],'old')

if __name__=='__main__':unittest.main()
