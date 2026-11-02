from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'engine'))
import mcdo_gateway


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.key = 'fixture-not-a-live-credential-' * 2
        self.state = Path(self.temp.name)
        (self.state / 'operator.key').write_text(self.key)
        self.client = mcdo_gateway.GatewayClient(self.state)
        self.client.authenticated_key = __import__('hashlib').sha256(self.key.encode()).digest()

    def test_fixed_gateway_and_origin_on_financial_requests_without_raw_key(self):
        self.client.opener = Mock()
        self.client.opener.open.return_value = BytesIO(b'{"data":{"state":"applying"}}')
        self.assertEqual(self.client.request('/runs/fixture/apply', {})['state'], 'applying')
        request = self.client.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, mcdo_gateway.GATEWAY + '/runs/fixture/apply')
        self.assertEqual(request.headers['Origin'], mcdo_gateway.ORIGIN)
        self.assertNotIn('Authorization', request.headers)

    def test_network_failure_does_not_replay_financial_post(self):
        self.client.opener = Mock()
        self.client.opener.open.side_effect = urllib.error.URLError('timeout after send')
        with self.assertRaisesRegex(RuntimeError, 'resume checks the server'):
            self.client.request('/runs/fixture/apply', {})
        self.assertEqual(self.client.opener.open.call_count, 1)

    def test_http_conflict_does_not_replay_apply(self):
        self.client.opener = Mock()
        self.client.opener.open.side_effect = urllib.error.HTTPError('https://fixed', 409, 'Conflict', {}, BytesIO(b'{"detail":"Run already applying"}'))
        with self.assertRaisesRegex(RuntimeError, 'already applying'):
            self.client.request('/runs/fixture/apply', {})
        self.assertEqual(self.client.opener.open.call_count, 1)

    def test_rejected_session_is_refreshed_once(self):
        unauthorized = urllib.error.HTTPError('https://fixed', 401, 'Expired', {}, BytesIO(b'{}'))
        with patch.object(self.client, '_call', side_effect=[unauthorized, {'state':'complete'}]) as call, patch.object(self.client, '_login') as login:
            self.assertEqual(self.client.request('/runs/fixture')['state'], 'complete')
        self.assertEqual(call.call_count, 2)
        login.assert_called_once()

    def test_arbitrary_destinations_and_query_injection_are_rejected(self):
        for path in ('https://other.invalid', '//other.invalid', '/runs?url=other', '/runs/../../secret'):
            with self.assertRaises(ValueError):
                self.client.request(path)

    def test_rotated_key_requires_new_session(self):
        (self.state/'operator.key').write_text('replacement-fixture-credential-' * 2)
        with patch.object(self.client, '_login') as login, patch.object(self.client, '_call', return_value={'authenticated':True}):
            self.client.request('/session')
        login.assert_called_once()


if __name__ == '__main__':
    unittest.main()
