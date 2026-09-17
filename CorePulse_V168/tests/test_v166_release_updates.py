"""Updater con red simulada y aplicación exclusivamente en directorios temporales."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch
import zipfile

from core import update_manager as um


class Response(io.BytesIO):
    headers = {}


def asset(name='CorePulse_V167.zip', data=b'package', digest=True):
    return um.ReleaseAsset(name, len(data), 'https://github.com/owner/repo/releases/download/V167/' + name,
                           'https://api.github.com/repos/owner/repo/releases/assets/1',
                           'sha256:' + hashlib.sha256(data).hexdigest() if digest else None)


def release(*assets, tag='V167', preview=False):
    return um.ReleaseInfo(tag, tag, '', preview, None, 'https://github.com/owner/repo/releases', tuple(assets))


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'COREPULSE_DATA_DIR': str(self.root / 'data'),
                                         'COREPULSE_CONFIG_DIR': str(self.root / 'config')})
        self.env.start()
        self.addCleanup(self.env.stop)

    def package(self, version='167'):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as z:
            z.writestr('CorePulse/main.py', 'print("test")')
            z.writestr('CorePulse/core/version.py', 'VERSION = ' + repr(version))
        return buffer.getvalue()

    def download(self, data=None):
        data = self.package() if data is None else data
        a = asset(data=data)
        return um.download_asset_verified(a, release(a), opener=lambda *a, **k: Response(data))

    def test_mode_selects_only_usable_package(self):
        zip_asset, installer = asset(), asset('CorePulse_Setup_V167.exe')
        notes = asset('CorePulse_notes.txt')
        self.assertIs(um.choose_asset(release(zip_asset, notes, installer), frozen=True), installer)
        self.assertIs(um.choose_asset(release(zip_asset, notes, installer), frozen=False), zip_asset)
        self.assertIsNone(um.choose_asset(release(zip_asset, notes), frozen=True))
        self.assertIsNone(um.choose_asset(release(installer, notes), frozen=False))

    def test_stable_default_preserves_explicit_development_preference(self):
        self.assertEqual(um.load_preferences()['channel'], um.CHANNEL_STABLE)
        self.assertTrue(um.save_preferences(channel=um.CHANNEL_INTERNAL))
        self.assertEqual(um.load_preferences()['channel'], um.CHANNEL_INTERNAL)
        self.assertEqual(um.choose_release([release(tag='V167'), release(tag='V168', preview=True)]).tag, 'V167')

    def test_stable_release_on_second_page_is_found(self):
        calls = []
        def opener(req, **_):
            calls.append(req.full_url)
            first = len(calls) == 1
            response = Response(json.dumps([{'tag_name': 'V170' if first else 'V169',
                'prerelease': first, 'assets': []}]).encode())
            response.headers = {'Link': '<ignored>; rel="next"'} if first else {}
            return response
        result = um.check_for_update(um.CHANNEL_STABLE, opener=opener)
        self.assertEqual(result['latest'].tag, 'V169')
        self.assertTrue(result['available'])
        self.assertTrue(calls[1].endswith('&page=2'))

    def test_legacy_download_also_rejects_unverified_package(self):
        with self.assertRaises(um.UpdateError):
            um.download_asset(asset(digest=False), release(), opener=lambda *a, **k: Response(b'package'))

    def test_checksum_is_for_exact_filename(self):
        digest = 'a' * 64
        self.assertIsNone(um._parse_checksum_text(digest + '  Other.zip', 'CorePulse.zip'))
        self.assertIsNone(um._parse_checksum_text(digest + '  CorePulse.zip.old', 'CorePulse.zip'))
        self.assertIsNone(um._parse_checksum_text(digest, 'CorePulse.zip'))
        self.assertEqual(um._parse_checksum_text(digest + ' *CorePulse.zip', 'CorePulse.zip'), digest)
        self.assertEqual(um._parse_checksum_text(digest, 'CorePulse.zip', allow_bare=True), digest)

    def test_sidecar_download_and_hash_failure(self):
        data = b'zip-content'
        a = asset(data=data, digest=False)
        side = asset(a.name + '.sha256', digest=False)
        def opener(req, **_):
            return Response((hashlib.sha256(data).hexdigest() + '  ' + a.name).encode()
                            if req.full_url.endswith('.sha256') else data)
        with patch.dict(os.environ, {'COREPULSE_GITHUB_TOKEN': ''}):
            result = um.download_asset_verified(a, release(a, side), opener=opener)
        self.assertTrue(result['verified'])
        with self.assertRaises(um.UpdateError):
            um.download_asset_verified(asset(), release(asset()), opener=lambda *a, **k: Response(b'bad'))
        self.assertFalse(list((self.root / 'data').rglob('*.part')))

    def test_cancellation_removes_partial_and_can_retry(self):
        cancel = threading.Event()
        data = b'x' * 400000
        a = asset(data=data)
        with self.assertRaisesRegex(um.UpdateError, 'cancelada'):
            um.download_asset_verified(a, release(a), opener=lambda *a, **k: Response(data),
                                      progress=lambda *_: cancel.set(), cancel=cancel)
        self.assertFalse(list((self.root / 'data').rglob('*.part')))
        self.assertFalse(list((self.root / 'data').rglob('*.zip')))
        cancel.clear()
        self.assertTrue(um.download_asset_verified(a, release(a), opener=lambda *a, **k: Response(data), cancel=cancel)['verified'])

    def test_download_paths_stay_in_updates(self):
        target = um._download_target(asset(), release(tag='../../elsewhere'))
        self.assertTrue(target.is_relative_to(um.updates_dir()))
        for name in ('../file.zip', 'C:\\file.zip', 'file.zip:stream', '..'):
            with self.assertRaises(um.UpdateError):
                um._download_target(asset(name), release())

    def test_token_not_sent_to_browser_download_or_redirect(self):
        with patch.dict(os.environ, {'COREPULSE_GITHUB_TOKEN': 'test-only-token'}):
            req = um._request('https://api.github.com/repos/x/y/releases')
            self.assertIsNotNone(req.get_header('Authorization'))
            self.assertIsNone(um._request('https://github.com/x/y').get_header('Authorization'))
            redirected = um._SafeRedirect().redirect_request(req, None, 302, '', {}, 'https://release-assets.githubusercontent.com/file')
            self.assertIsNone(redirected.get_header('Authorization'))
        with self.assertRaises(um.UpdateError):
            um._request('http://github.com/x/y')

    def test_tampered_package_never_launches(self):
        data = b'executable'
        a = asset('CorePulse_Setup_V167.exe', data)
        result = um.download_asset_verified(a, release(a), opener=lambda *a, **k: Response(data))
        Path(result['path']).write_bytes(b'changed')
        with patch.object(um.os, 'startfile', create=True) as launch:
            with self.assertRaises(um.UpdateError):
                um.launch_installer(result)
            launch.assert_not_called()

    def test_stage_checks_version_without_executing_it(self):
        result = self.download()
        staged = um.stage_source_release(result)
        self.assertTrue(Path(staged['entry']).is_file())
        wrong = self.download(self.package('999'))
        with self.assertRaisesRegex(um.UpdateError, 'versión'):
            um.stage_source_release(wrong)

    def test_zip_paths_links_and_collisions_rejected(self):
        for names in [('..\\outside',), ('/absolute',), ('main.py', 'MAIN.py'), ('name:stream',)]:
            with self.subTest(names=names):
                archive = self.root / 'bad.zip'
                with zipfile.ZipFile(archive, 'w') as z:
                    for name in names: z.writestr(name, 'bad')
                with self.assertRaises(um.UpdateError):
                    um._safe_extract_zip(archive, self.root / 'extract')

    def prepare_helper(self):
        root = self.root / 'application'
        (root / 'core').mkdir(parents=True)
        (root / 'core/version.py').write_text('VERSION = "166"')
        (root / 'main.py').write_text('old')
        (root / 'data').mkdir()
        (root / 'data/user.txt').write_text('keep')
        result = self.download()
        with patch.object(um, 'source_root', return_value=root), patch.object(um, 'installation_mode', return_value='source-portable'):
            plan = um.prepare_source_update(result)
        ns = {'__name__': 'isolated_helper'}
        exec(compile(um._UPDATE_HELPER_SCRIPT, 'helper', 'exec'), ns)
        ns['wait_pid'] = Mock()
        ns['relaunch'] = Mock()
        return root, plan, ns

    def invoke(self, plan, ns):
        with patch('sys.argv', ['helper', plan['plan']]): ns['main']()
        return json.loads(Path(plan['status']).read_text())

    def test_helper_applies_and_preserves_user_data(self):
        root, plan, ns = self.prepare_helper()
        self.assertTrue(self.invoke(plan, ns)['ok'])
        self.assertIn('test', (root / 'main.py').read_text())
        self.assertEqual((root / 'data/user.txt').read_text(), 'keep')
        ns['relaunch'].assert_called_once()

    def test_helper_rejects_changed_stage_and_backup_before_deletion(self):
        root, plan, ns = self.prepare_helper()
        Path(plan['incoming_root'], 'main.py').write_text('changed')
        self.assertFalse(self.invoke(plan, ns)['ok'])
        self.assertEqual((root / 'main.py').read_text(), 'old')
        ns['relaunch'].assert_not_called()

    def test_helper_rejects_modified_backup(self):
        root, plan, ns = self.prepare_helper()
        Path(plan['backup_zip']).write_bytes(b'broken')
        self.assertFalse(self.invoke(plan, ns)['ok'])
        self.assertEqual((root / 'main.py').read_text(), 'old')

    def test_helper_rejects_checkout_created_after_preparation(self):
        root, plan, ns = self.prepare_helper()
        (root / '.git').mkdir()
        self.assertFalse(self.invoke(plan, ns)['ok'])
        self.assertEqual((root / 'main.py').read_text(), 'old')

    def test_helper_wait_failure_does_not_modify_or_relaunch_running_app(self):
        root, plan, ns = self.prepare_helper()
        ns['wait_pid'].side_effect = RuntimeError('still running')
        self.assertFalse(self.invoke(plan, ns)['ok'])
        self.assertEqual((root / 'main.py').read_text(), 'old')
        ns['relaunch'].assert_not_called()

    def test_helper_rolls_back_when_copy_fails(self):
        root, plan, ns = self.prepare_helper()
        def fail_copy(incoming, target):
            (target / 'main.py').write_text('incomplete')
            raise OSError('simulated locked file')
        ns['copy_incoming'] = fail_copy
        self.assertFalse(self.invoke(plan, ns)['ok'])
        self.assertEqual((root / 'main.py').read_text(), 'old')
        self.assertEqual((root / 'data/user.txt').read_text(), 'keep')


class UpdatePageTests(unittest.TestCase):
    def page(self):
        from gui import update_dialog as ui
        class Value:
            def __init__(self): self.value = None
            def set(self, value): self.value = value
            def get(self): return self.value
        page = ui.UpdatePanel.__new__(ui.UpdatePanel)
        page._alive = page._visible = True
        page.busy = True
        page._download_cancel = threading.Event()
        page.frame = types.SimpleNamespace(after=lambda delay, cb: cb())
        page.primary = Mock()
        page.check_button = Mock()
        page.channel = Mock()
        page._set_notes = Mock()
        for name in ('status_var', 'progress_text_var', 'release_var', 'meta_var', 'channel_var', 'progress_var'):
            setattr(page, name, Value())
        page.channel_var.set('Estable')
        page.result = {'available': True, 'latest': release(asset())}
        page.asset = asset()
        page.download = {'old': True}
        page.staged = {'old': True}
        page.app = Mock()
        return page

    def test_hidden_check_completion_releases_busy_and_keeps_result(self):
        page = self.page()
        page.set_active(False)
        result = {'available': True, 'latest': release(asset())}
        page._call_ui(lambda: page._finish_check(result))
        self.assertFalse(page.busy)
        self.assertIs(page.result, result)
        self.assertIsNone(page.download)
        page.set_active(True)
        self.assertFalse(page.busy)

    def test_empty_release_clears_previous_package(self):
        page = self.page()
        page._finish_check({'latest': None, 'available': False})
        self.assertIsNone(page.asset)
        self.assertIsNone(page.download)
        self.assertIsNone(page.staged)

    def test_cancel_failure_is_retryable_without_error_dialog(self):
        page = self.page()
        page.cancel_download()
        with patch('gui.update_dialog.cp_error') as dialog:
            page._fail('Download', um.UpdateError('Descarga cancelada'))
        self.assertFalse(page.busy)
        self.assertEqual(page.primary.configure.call_args.kwargs['state'], 'normal')
        dialog.assert_not_called()

    def test_late_completion_after_cancel_does_not_enable_install(self):
        page = self.page()
        page.cancel_download()
        page._finish_download({'verified': True})
        self.assertIsNone(page.download)
        self.assertEqual(page.primary.configure.call_args.kwargs['text'], 'Reintentar descarga')


if __name__ == '__main__':
    unittest.main()
