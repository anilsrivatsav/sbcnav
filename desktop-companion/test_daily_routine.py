from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from daily_routine import tick, IST


class DailyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'daily.json'
        self.now = datetime(2026,11,26,10,tzinfo=IST)
        self.controller = Mock()
        self.status = {'configured':True,'busy':False,'deskflow_busy':False,'phase':'ready'}
        self.controller.snapshot.side_effect = lambda: self.status
        self.deskflow = Mock()
        self.deskflow.schedule_pdf_status.return_value = {}

    def test_daily_starts_only_routine_once_then_only_upcoming_auctions(self):
        self.assertEqual(tick(self.controller,self.deskflow,self.path,self.now),'receipts')
        self.controller.command.assert_called_once_with('start')
        self.assertEqual(tick(self.controller,self.deskflow,self.path,self.now),'attention')
        self.status.update(run={'state':'complete'},end='26/11/2026',phase='complete')
        self.assertEqual(tick(self.controller,self.deskflow,self.path,self.now),'auctions')
        self.assertEqual(self.deskflow.command.call_args.args[0],'schedule-pdf')
        self.assertEqual(set(self.deskflow.command.call_args.args[1]),{'request_id'})
        self.assertEqual(tick(self.controller,self.deskflow,self.path,self.now),'attention')
        self.deskflow.schedule_pdf_status.return_value = {'request':{'phase':'ready','checked_at':'2026-11-26T10:10:00+05:30'}}
        self.assertEqual(tick(self.controller,self.deskflow,self.path,self.now),'complete')

    def test_busy_paused_and_early_runs_are_left_alone(self):
        self.status['busy'] = True
        self.assertEqual(tick(self.controller,self.deskflow,self.path,self.now),'busy')
        self.status.update(busy=False,phase='paused')
        self.assertEqual(tick(self.controller,self.deskflow,self.path,self.now),'attention')
        self.assertEqual(tick(self.controller,self.deskflow,self.path,self.now.replace(hour=8)),'not_due')
        self.controller.command.assert_not_called()
        self.deskflow.command.assert_not_called()
