import ast
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from performance import power_manager as pm
from performance.profile_manager import PerformanceProfileManager
from tests.test_managed_power_plans import Windows
from tests.test_windows_power_plan_sync import Boost, Detector


class BalancedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'registry.json'
        self.windows = Windows()
        self.restorer = Mock(side_effect=self.restore)
        self.power = pm.PowerManager(self.windows, registry_path=self.path,
            description_reader=lambda _: None, scheme_restorer=self.restorer)
        self.power.available = lambda: True

    def restore(self, guid):
        self.assertEqual(guid, pm.BALANCED_GUID)
        self.windows.plans[guid] = 'Equilibrado'
        return {'success': True}

    def test_absent_balanced_recovers_despite_previous_failed_creation(self):
        del self.windows.plans[pm.BALANCED_GUID]
        self.windows.plans['11111111-1111-1111-1111-111111111111'] = 'Mi plan personalizado'
        self.power.managed_plans.save({'version': 1, 'preferred': {}, 'plans': {
            '097f0ae3-dc71-5123-825d-c91cae86611a': {'mode': 'BALANCED', 'base': pm.BALANCED_GUID,
                                                  'owned': True, 'state': 'failed', 'error': 'old error'}}})
        for _ in range(10):
            result = self.power.ensure_mode_scheme('BALANCED')
            self.assertTrue(result['success'], result)
            self.assertEqual(result['guid'], pm.BALANCED_GUID)
        self.restorer.assert_called_once_with(pm.BALANCED_GUID)
        self.assertEqual(self.windows.count('/duplicatescheme'), 0)
        self.assertEqual(self.windows.count('/delete'), 0)
        self.assertIn('Mi plan personalizado', self.windows.plans.values())

    def test_present_balanced_never_reset(self):
        self.assertTrue(self.power.ensure_mode_scheme('BALANCED')['success'])
        self.restorer.assert_not_called()

    def test_restore_failure_preserves_error_and_other_plans(self):
        del self.windows.plans[pm.BALANCED_GUID]
        self.restorer.side_effect = None
        self.restorer.return_value = {'success': False, 'message': 'Access denied (5)'}
        result = self.power.ensure_mode_scheme('BALANCED')
        self.assertFalse(result['success'])
        self.assertIn('Access denied', result['message'])
        self.assertEqual(self.windows.count('/duplicatescheme'), 0)

    def test_restore_success_without_plan_is_not_success(self):
        del self.windows.plans[pm.BALANCED_GUID]
        self.restorer.side_effect = None
        self.restorer.return_value = {'success': True}
        self.assertFalse(self.power.ensure_mode_scheme('BALANCED')['success'])

    def test_snapshot_reads_three_settings_with_one_command(self):
        result = self.power.snapshot_scheme(pm.BALANCED_GUID)
        self.assertEqual(len(result['settings']), 3)
        self.assertEqual(self.windows.count('/qh'), 1)

    def test_ui_status_does_not_wait_for_energy_worker(self):
        manager = PerformanceProfileManager(self.power, Detector(),
            backup_path=Path(self.tmp.name) / 'backup.json', start_thread=False,
            register_atexit=False, game_boost=Boost())
        initial = manager.status()
        locked, release, done = threading.Event(), threading.Event(), threading.Event()
        def operation():
            with manager.lock:
                locked.set()
                release.wait(3)
        worker = threading.Thread(target=operation)
        worker.start()
        try:
            self.assertTrue(locked.wait(1))
            results = []
            reader = threading.Thread(target=lambda: (results.append(manager.status()), done.set()))
            reader.start()
            self.assertTrue(done.wait(.5), 'UI blocked by powercfg worker')
            self.assertEqual(results[0]['requested_mode'], initial['requested_mode'])
        finally:
            release.set()
            worker.join()


class AudioModuleTests(unittest.TestCase):
    def test_navigation_uses_existing_health_center(self):
        from gui.audio_test_panel import open_audio_test
        app = Mock()
        open_audio_test(app)
        app.open_health_center.assert_called_once_with(tab='audio')

    def test_audio_is_frame_and_has_no_second_scroll_or_window(self):
        source = (Path(__file__).resolve().parents[1] / 'gui/audio_test_panel.py').read_text(encoding='utf-8')
        self.assertIn('class AudioTestPanel(ctk.CTkFrame)', source)
        self.assertNotIn('CTkToplevel', source)
        self.assertNotIn('CTkScrollableFrame', source)
        ast.parse(source)

    def test_unrelated_jobs_do_not_rebuild_audio(self):
        from gui.health_center_panel import HealthCenterPanel
        obj = object.__new__(HealthCenterPanel)
        obj._alive = True
        obj._tab = 'audio'
        obj._render = Mock()
        obj._request_render()
        obj._render.assert_not_called()


if __name__ == '__main__':
    unittest.main()
