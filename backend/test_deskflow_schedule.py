import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import deskflow_router


class PublishedScheduleTests(unittest.TestCase):
    def test_heartbeat_retains_the_latest_verified_schedule(self):
        previous = {
            'phase': 'ready',
            'checked_at': '2026-11-25T16:39:00+05:30',
            'lots': [{'lot': 'SBC-LOT-1'}],
        }
        row = SimpleNamespace(overview={'schedule_pdf_requests': {'previous': previous}},
                              last_seen_at=None, command_id=None)
        database = MagicMock()
        database.return_value.__enter__.return_value.get.return_value = row

        with patch.object(deskflow_router, 'SessionLocal', database), patch.object(deskflow_router, '_row', return_value=row):
            deskflow_router.agent_sync({'overview': {'schedule_pdf_requests': {}}, 'software_update': {}})
            self.assertEqual(deskflow_router.schedule_pdf_status(None)['lots'], previous['lots'])

            newer_empty = {'phase': 'ready', 'checked_at': '2026-11-25T11:10:00+00:00', 'lots': []}
            deskflow_router.agent_sync({
                'overview': {'schedule_pdf_requests': {'newer': newer_empty, 'previous': previous,
                                                        'failed': {'phase': 'error'}}},
                'software_update': {},
            })
            self.assertEqual(deskflow_router.schedule_pdf_status(None)['checked_at'], newer_empty['checked_at'])
            self.assertEqual(deskflow_router.schedule_pdf_status(None)['lots'], [])
            self.assertEqual(deskflow_router.schedule_pdf_status('previous')['lots'], previous['lots'])
