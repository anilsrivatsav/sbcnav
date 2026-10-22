import ctypes
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import server
import state_store


class StateStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'state.json'
        state_store.write_state(self.path, {'phase': 'ready'})

    def tearDown(self):
        self.directory.cleanup()

    def test_transient_windows_denial_retries_without_losing_checkpoint(self):
        replace = os.replace
        failures = [PermissionError(5, 'Access is denied'), PermissionError(32, 'Sharing violation')]
        def locked(source, target):
            if failures:
                self.assertEqual(json.loads(self.path.read_text()), {'phase': 'ready'})
                raise failures.pop()
            return replace(source, target)
        with patch.object(state_store.os, 'replace', side_effect=locked), patch.object(state_store.time, 'sleep'):
            self.assertFalse(state_store.write_state(self.path, {'phase': 'collecting', 'run': 'saved'}))
        self.assertEqual(state_store.read_state(self.path)['run'], 'saved')
        self.assertFalse(list(self.path.parent.glob('*.tmp')))

    def test_persistent_primary_lock_uses_recovery_and_restart_reads_it(self):
        replace = os.replace
        def locked(source, target):
            if Path(target) == self.path:
                raise PermissionError(5, 'Access is denied')
            return replace(source, target)
        with patch.object(state_store.os, 'replace', side_effect=locked), patch.object(state_store.time, 'sleep'):
            self.assertTrue(state_store.write_state(self.path, {'phase': 'collecting', 'run': 'saved'}))
        self.assertEqual(json.loads(self.path.read_text())['phase'], 'ready')
        self.assertEqual(state_store.read_state(self.path)['run'], 'saved')
        with patch.object(server, 'STATE', self.path.parent):
            resumed = server.Controller()
        self.assertEqual(resumed.state['phase'], 'interrupted')
        self.assertEqual(resumed.state['run'], 'saved')
        state_store.write_state(self.path, {'phase': 'complete'})
        self.assertEqual(state_store.read_state(self.path)['phase'], 'complete')
        self.assertFalse(self.path.with_name('state.recovery.json').exists())

    def test_corrupt_primary_falls_back_to_valid_recovery(self):
        self.path.with_name('state.recovery.json').write_text('{"run": "saved"}')
        self.path.write_text('{broken')
        self.assertEqual(state_store.read_state(self.path), {'run': 'saved'})

    def test_unwritable_primary_and_recovery_fail_without_truncating_primary(self):
        with patch.object(state_store.os, 'replace', side_effect=PermissionError(5, 'Access is denied')), patch.object(state_store.time, 'sleep'):
            with self.assertRaises(PermissionError):
                state_store.write_state(self.path, {'phase': 'complete'})
        self.assertEqual(json.loads(self.path.read_text()), {'phase': 'ready'})
        self.assertFalse(list(self.path.parent.glob('*.tmp')))

    def test_controller_logging_continues_with_recovery_checkpoint(self):
        replace = os.replace
        def locked(source, target):
            if Path(target) == self.path:
                raise PermissionError(5, 'Access is denied')
            return replace(source, target)
        with patch.object(server, 'STATE', self.path.parent):
            controller = server.Controller()
            with patch.object(state_store.os, 'replace', side_effect=locked), patch.object(state_store.time, 'sleep'):
                controller.save(phase='collecting', run={'run_id': 'saved'})
                controller.log('Verifying invoice ES26TEST')
            self.assertEqual(controller.snapshot()['phase'], 'collecting')
            self.assertIn('recovery checkpoint', controller.snapshot()['persistence_warning'])
            self.assertEqual(state_store.read_state(self.path)['run']['run_id'], 'saved')

    @unittest.skipUnless(os.name == 'nt', 'Windows sharing semantics required')
    def test_real_windows_reader_lock_is_retried(self):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateFileW(str(self.path), 0x80000000, 3, None, 3, 0, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        timer = threading.Timer(.15, lambda: kernel.CloseHandle(handle))
        timer.start()
        try:
            self.assertFalse(state_store.write_state(self.path, {'phase': 'complete'}))
        finally:
            timer.join()
        self.assertEqual(state_store.read_state(self.path)['phase'], 'complete')


if __name__ == '__main__':
    unittest.main()
