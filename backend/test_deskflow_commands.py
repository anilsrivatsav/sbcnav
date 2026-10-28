import os
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
import unittest
from contextlib import nullcontext
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import deskflow_router as api


class ReviewCommandTests(unittest.TestCase):
    def setUp(self):
        self.row = SimpleNamespace(last_seen_at=datetime.now(timezone.utc),command_id=None,command={})
        self.session = patch.object(api,'SessionLocal',SimpleNamespace(begin=lambda:nullcontext(None)))
        self.lookup = patch.object(api,'_row',return_value=self.row)
        self.session.start();self.lookup.start()
        self.addCleanup(self.session.stop);self.addCleanup(self.lookup.stop)

    def test_review_payload_is_queued_with_revision_intact(self):
        payload={'key':'C|L','revision':'evidence-revision','proposal_revision':'proposal-revision'}
        self.assertTrue(api.command('review-proposal',payload)['queued'])
        self.assertEqual(self.row.command,{'action':'review-proposal','payload':payload})

    def test_unknown_actions_fields_and_oversized_reviews_are_rejected(self):
        for action,payload in [('execute',{}),('save-reviewed',{'path':'other.xlsx'}),
            ('save-review',{'key':'C|L','revision':'v','command':'arbitrary'}),
            ('save-review',{'key':'C|L','revision':'v','inputs':{'source':'x'*50000}}),
            ('save-review',{'key':'C|L','revision':''})]:
            with self.assertRaises(HTTPException) as raised:api.command(action,payload)
            self.assertEqual(raised.exception.status_code,400)
        self.assertIsNone(self.row.command_id)

    def test_pending_command_is_preserved(self):
        self.row.command_id='old-command';self.row.command={'action':'history'}
        with self.assertRaises(HTTPException) as raised:api.command('save-reviewed',{})
        self.assertEqual(raised.exception.status_code,409)
        self.assertEqual(self.row.command,{'action':'history'})

    def test_disconnected_desktop_cannot_queue_a_review(self):
        self.row.last_seen_at=None
        with self.assertRaises(HTTPException) as raised:api.command('save-reviewed',{})
        self.assertEqual(raised.exception.status_code,503)

    def test_review_routes_require_browser_authentication(self):
        app=FastAPI();app.include_router(api.router)
        with patch.dict(os.environ,{'MCDO_ADMIN_TOKEN':'fixture-token-that-is-longer-than-32-characters'}):
            with TestClient(app) as client:
                response=client.post('/api/deskflow/save-reviewed',json={})
        self.assertEqual(response.status_code,401)
        self.assertIsNone(self.row.command_id)


if __name__=='__main__':unittest.main()
