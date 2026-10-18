import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import server


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.state = patch.object(server, 'STATE', Path(self.folder.name))
        self.state.start()
        (server.STATE / 'operator.key').write_text('test-placeholder-not-a-real-key')
        self.controller = server.Controller()

    def tearDown(self):
        self.state.stop()
        self.folder.cleanup()

    def test_restart_retains_run_without_claiming_completion(self):
        self.controller.save(phase='collecting', run={'run_id': 'saved', 'state': 'awaiting_ireps'})
        restored = server.Controller().snapshot()
        self.assertEqual(restored['phase'], 'interrupted')
        self.assertEqual(restored['run']['run_id'], 'saved')
        self.assertFalse(restored['busy'])
        self.assertNotIn('test-placeholder', json.dumps(restored))

    def test_duplicate_start_rejected(self):
        self.controller.thread = unittest.mock.Mock()
        self.controller.thread.is_alive.return_value = True
        with self.assertRaisesRegex(RuntimeError, 'already running'):
            self.controller.command('start')

    def test_resume_after_lost_apply_response_reads_server_first(self):
        self.controller.save(run={'run_id': 'saved'})
        complete = {'run_id': 'saved', 'state': 'complete'}
        with patch.object(server, 'request', side_effect=[{}, complete]) as api:
            self.controller.work('resume')
        self.assertEqual(self.controller.snapshot()['phase'], 'complete')
        self.assertEqual(api.call_count, 2)

    def test_resume_pending_preview_applies_once(self):
        self.controller.save(run={'run_id': 'saved'})
        with patch.object(server, 'request', side_effect=[{}, {'run_id': 'saved', 'state': 'preview_ready'}, {}, {'run_id': 'saved', 'state': 'complete'}]) as api:
            self.controller.work('resume')
        self.assertEqual(self.controller.snapshot()['phase'], 'complete')
        self.assertEqual([call.args[0] for call in api.call_args_list].count('/runs/saved/apply'), 1)

    def test_resume_incomplete_scan_does_not_write(self):
        self.controller.save(run={'run_id': 'saved'})
        with patch.object(server, 'request', side_effect=[{}, {'run_id': 'saved', 'state': 'awaiting_ireps'}]) as api:
            self.controller.work('resume')
        self.assertEqual(self.controller.snapshot()['phase'], 'error')
        self.assertEqual(api.call_count, 2)

    def test_origin_and_dns_rebinding_protection(self):
        handler = object.__new__(server.Handler)
        handler.headers = {'Host': f'127.0.0.1:{server.PORT}', 'Origin': server.ORIGIN}
        self.assertTrue(handler.permitted())
        for host, origin in [(f'evil.test:{server.PORT}',server.ORIGIN),(f'127.0.0.1:{server.PORT}','https://evil.test'),(f'127.0.0.1:{server.PORT}',None)]:
            handler.headers = {'Host': host, 'Origin': origin}
            self.assertFalse(handler.permitted())

    def test_sheet_serial_due_dates_are_normalized_for_existing_invoices(self):
        from incremental import invoice_needed
        from datetime import date
        due = server.collector_due_dates({'SBC-RT-YPR': 46344, 'EMPTY': None})
        self.assertEqual(due['SBC-RT-YPR'], date(2026, 11, 18))
        self.assertIsNone(due['EMPTY'])
        self.assertFalse(invoice_needed('ES26OLD','SBC-RT-YPR','19/08/2026',{'ES26OLD'},due))
        self.assertTrue(invoice_needed('ES26OLD','SBC-RT-YPR','18/11/2026',{'ES26OLD'},due))


if __name__ == '__main__':
    unittest.main()
