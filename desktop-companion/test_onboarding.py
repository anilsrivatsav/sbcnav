import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from http.server import ThreadingHTTPServer
import portable
import server
from rp import onboarding
from rp.setup_download import FILENAME, installer_path


class OnboardingTests(unittest.TestCase):
    def test_existing_components_are_kept_and_actual_sign_in_is_checked(self):
        connect, start, log = Mock(), Mock(return_value={'configured': True, 'busy': False}), Mock()
        with patch.object(onboarding, 'prerequisites', return_value={'chrome': True, 'signer': True}), patch.object(onboarding, 'install_component') as install, patch.object(onboarding, 'check_ireps') as sign_in:
            onboarding.provision(None, connect, start, Path('.'), log)
        connect.assert_called_once_with(None)
        install.assert_not_called()
        sign_in.assert_called_once()

    def test_missing_components_install_before_sign_in(self):
        with patch.object(onboarding, 'prerequisites', return_value={'chrome': False, 'signer': False}), patch.object(onboarding, 'install_component') as install, patch.object(onboarding, 'check_ireps') as sign_in:
            onboarding.provision('connection', Mock(), Mock(return_value={'configured': True}), Path('.'), Mock())
        self.assertEqual([c.args[0] for c in install.call_args_list], ['chrome', 'signer'])
        sign_in.assert_called_once()

    def test_bad_connection_never_installs_components_or_opens_ireps(self):
        with patch.object(onboarding, 'install_component') as install, patch.object(onboarding, 'check_ireps') as sign_in:
            with self.assertRaisesRegex(ValueError, 'not authorised'):
                onboarding.provision(None, Mock(side_effect=ValueError('not authorised')), Mock(), Path('.'), Mock())
        install.assert_not_called()
        sign_in.assert_not_called()

    def test_setup_does_not_interfere_with_a_running_update(self):
        with patch.object(onboarding, 'prerequisites', return_value={'chrome': True, 'signer': True}), patch.object(onboarding, 'check_ireps') as sign_in:
            with self.assertRaisesRegex(ValueError, 'update is running'):
                onboarding.provision(None, Mock(), Mock(return_value={'configured': True, 'busy': True}), Path('.'), Mock())
        sign_in.assert_not_called()

    def test_signer_download_is_pinned_and_changed_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Signer.msi'
            path.write_bytes(b'fixture component')
            with self.assertRaisesRegex(ValueError, 'download has changed'):
                onboarding.verify_component('signer', path)
            with patch.object(onboarding, 'SIGNER_SHA256', hashlib.sha256(path.read_bytes()).hexdigest()):
                onboarding.verify_component('signer', path)

    def test_untrusted_chrome_publisher_is_rejected(self):
        fake = Mock(returncode=0, stdout=json.dumps({'status': 'Valid', 'publisher': 'Unknown publisher'}))
        with patch.object(onboarding.subprocess, 'run', return_value=fake):
            with self.assertRaisesRegex(ValueError, 'signature could not be verified'):
                onboarding.verify_component('chrome', Path('Chrome.msi'))

    def test_google_signature_uses_windows_builtin_security_module_path(self):
        fake = Mock(returncode=0, stdout=json.dumps({'status': 'Valid', 'publisher': 'CN=Google LLC, O=Google LLC'}))
        with patch.object(onboarding.subprocess, 'run', return_value=fake) as run:
            onboarding.verify_component('chrome', Path('Chrome.msi'))
        self.assertTrue(run.call_args.kwargs['env']['PSModulePath'].replace('\\', '/').endswith('WindowsPowerShell/v1.0/Modules'))

    def test_protocol_opens_setup_without_collecting_or_typing_keys(self):
        with patch.object(portable.sys, 'argv', ['app', 'sbcnav-updater://setup']), patch.object(portable, 'setup') as setup, patch.object(portable, 'start_service') as start:
            portable.main()
        setup.assert_called_once()
        start.assert_not_called()


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        self.patch = patch.object(server, 'STATE', self.state)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.data = b'MZfixture private installer'
        (self.state / 'operator.key').write_text('fixture-operator-key-not-a-real-secret')
        folder = self.state / 'Windows setup'
        folder.mkdir()
        (folder / FILENAME).write_bytes(self.data)
        (folder / 'installer.json').write_text(json.dumps({'filename': FILENAME, 'size': len(self.data)}))
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.port_patch = patch.object(server, 'PORT', self.http.server_port)
        self.port_patch.start()
        self.addCleanup(self.port_patch.stop)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)

    def request(self, path='/windows-setup', origin=server.ORIGIN, body='{}'):
        client = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        client.request('POST', path, body=body, headers={'Origin': origin, 'Content-Type': 'application/json'})
        response = client.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        client.close()
        return result

    def test_download_is_attachment_and_exact_bytes_without_caching(self):
        code, headers, body = self.request()
        self.assertEqual(code, 200)
        self.assertEqual(body, self.data)
        self.assertIn('attachment', headers['Content-Disposition'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['Access-Control-Allow-Origin'], server.ORIGIN)

    def test_other_website_cannot_download_the_private_installer(self):
        for origin in ('https://untrusted.invalid', 'http://localhost:3000'):
            code, _, body = self.request(origin=origin)
            self.assertEqual(code, 403)
            self.assertNotIn(self.data, body)

    def test_no_path_selection_or_nonempty_request_allowed(self):
        self.assertEqual(self.request(body='{"path":"operator.key"}')[0], 400)
        self.assertEqual(self.request(path='/windows-setup/../operator.key')[0], 404)

    def test_unconfigured_pc_cannot_offer_a_private_download(self):
        (self.state / 'operator.key').unlink()
        self.assertIsNone(installer_path(self.state))
        self.assertEqual(self.request()[0], 404)

    def test_partial_installer_is_not_offered(self):
        (self.state / 'Windows setup' / FILENAME).write_bytes(b'MZtruncated')
        self.assertIsNone(installer_path(self.state))


if __name__ == '__main__':
    unittest.main()
