import ast
import copy
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch

from gui.widget_updates import configure_changed, set_changed


class Widget:
    def __init__(self):
        self.values = {}
        self.writes = 0
        self.value = None
    def cget(self, key):
        return self.values.get(key)
    def configure(self, **kwargs):
        self.values.update(kwargs)
        self.writes += 1
    def get(self):
        return self.value
    def set(self, value):
        self.value = value
        self.writes += 1
    def winfo_manager(self):
        return 'pack'
    def pack_forget(self):
        pass


class UpdateTests(unittest.TestCase):
    def test_identical_updates_do_not_redraw(self):
        widget = Widget()
        for _ in range(1000):
            configure_changed(widget, text='CPU', text_color='cyan')
        self.assertEqual(widget.writes, 1)
        configure_changed(widget, text='GPU', text_color='cyan')
        self.assertEqual(widget.writes, 2)

    def test_external_theme_update_is_not_hidden_by_cache(self):
        widget = Widget()
        configure_changed(widget, text_color='cyan')
        widget.configure(text_color='red')
        configure_changed(widget, text_color='cyan')
        self.assertEqual(widget.values['text_color'], 'cyan')
        self.assertEqual(widget.writes, 3)

    def test_sequence_colors_and_unqueryable_options(self):
        widget = Widget()
        widget.values['text_color'] = ['black', 'white']
        configure_changed(widget, text_color=('black', 'white'))
        self.assertEqual(widget.writes, 0)
        widget.cget = Mock(side_effect=ValueError())
        configure_changed(widget, special=123)
        self.assertEqual(widget.values['special'], 123)

    def test_failure_is_retryable_and_not_cached(self):
        widget = Widget()
        original = widget.configure
        widget.configure = Mock(side_effect=RuntimeError())
        with self.assertRaises(RuntimeError):
            configure_changed(widget, text='test')
        widget.configure = original
        self.assertTrue(configure_changed(widget, text='test'))

    def test_progress_preserves_real_changes(self):
        widget = Widget()
        for value in (.5, .5, .501, .501, 0.):
            set_changed(widget, value)
        self.assertEqual(widget.writes, 3)
        self.assertEqual(widget.value, 0.)

    def test_real_telemetry_method_repeated_sample_avoids_writes(self):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / 'main.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'App')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'apply_telemetry_to_ui')
        ns = {'COLOR_RAM': 'green', 'COLOR_TEXT_DIM': 'gray'}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'main.py', 'exec'), ns)
        app = types.SimpleNamespace(is_running=True, winfo_exists=lambda: True,
            session_trend_collector=None, update_disks_ui=Mock(), _log_throttled_exception=Mock(),
            _dashboard_telemetry_wrapped=True, _live_health_binding_active=True)
        names = ('lbl_cpu_title','lbl_cpu','lbl_cpu_temp','lbl_ram','lbl_ram_gb','lbl_gpu_title',
                 'lbl_gpu','lbl_gpu_temp','bar_cpu','bar_ram','bar_gpu','lbl_health_val','lbl_health_status')
        for name in names:
            setattr(app, name, Widget())
        sample = dict(cpu_name='CPU', gpu_name='GPU', cpu_usage=10., ram_usage=40., gpu_usage=5.,
                      cpu_temp=50., gpu_temp=40., ram_used_gb=8., ram_total_gb=16.)
        with patch.dict('sys.modules', {'core.telemetry': types.SimpleNamespace(calculate_preliminary_score=lambda *args: 95.)}):
            fn = ns['apply_telemetry_to_ui']
            fn(app, sample, [])
            initial = sum(getattr(app, n).writes for n in names)
            for _ in range(99):
                fn(app, sample, [])
            self.assertEqual(sum(getattr(app, n).writes for n in names), initial)
            self.assertEqual(app._telemetry_ui_apply_count, 100)
            changed = dict(sample, cpu_usage=11.)
            fn(app, changed, [])
            self.assertEqual(app.lbl_cpu.values['text'], '11.0%')
            self.assertEqual(app.bar_cpu.value, .11)
        app._log_throttled_exception.assert_not_called()

    def test_thermal_calculations_preserved_without_intermediate_paint(self):
        from gui.thermal_health_binding import apply_thermal_health_semantics
        result = {'score': 44., 'severity': 'CRITICAL', 'status': 'HOT', 'reasons': ['hot']}
        app = types.SimpleNamespace(apply_telemetry_to_ui=Mock(), latest_score=95.,
                                    _live_health_binding_active=True, lbl_health_val=Widget())
        with patch('gui.thermal_health_binding.evaluate_current_health', return_value=result):
            apply_thermal_health_semantics(app)
            app.apply_telemetry_to_ui({}, [])
        self.assertEqual(app.current_health, result)
        self.assertEqual(app.latest_score, 44.)
        self.assertEqual(app.lbl_health_val.writes, 0)

    def test_boost_status_does_not_wait_for_worker(self):
        from performance.game_boost import GameBoostOptimizer
        with tempfile.TemporaryDirectory() as td, \
                patch.object(GameBoostOptimizer, '_recover_pending_runtime_backup'), \
                patch.object(GameBoostOptimizer, '_recover_pending_process_backup'):
            root = Path(td)
            boost = GameBoostOptimizer(config_path=root/'config.json',
                runtime_backup_path=root/'runtime.json', process_backup_path=root/'process.json')
            initial = boost.status()
            locked, release, done = threading.Event(), threading.Event(), threading.Event()
            def worker():
                with boost.lock:
                    locked.set()
                    release.wait(3)
            thread = threading.Thread(target=worker)
            thread.start()
            try:
                self.assertTrue(locked.wait(1))
                results = []
                reader = threading.Thread(target=lambda: (results.append(boost.status()), done.set()))
                reader.start()
                self.assertTrue(done.wait(.5))
                self.assertEqual(results[0], initial)
                results[0]['settings']['custom'] = True
                self.assertNotIn('custom', boost._status_cache['settings'])
            finally:
                release.set()
                thread.join()

    def test_overlay_idle_status_does_not_repaint_unchanged_controls(self):
        from gui.overlay_config_panel import OverlayConfigPanel
        panel = object.__new__(OverlayConfigPanel)
        panel.app = types.SimpleNamespace(overlay_window=None)
        names = ('status_badge', 'lbl_rtss', 'lbl_app', 'lbl_policy', 'btn_toggle')
        for name in names:
            setattr(panel, name, Widget())
        for _ in range(100):
            panel._refresh_status()
        self.assertEqual(sum(getattr(panel, name).writes for name in names), 5)
        panel.app.overlay_window = types.SimpleNamespace(winfo_exists=lambda: True,
            get_status=lambda: {'rtss_available': True, 'rtss_version': 1, 'active_app': {'name': 'Game'}})
        panel._refresh_status()
        self.assertEqual(panel.status_badge.values['text'], 'ACTIVO')
        self.assertEqual(panel.lbl_app.values['text'], 'Juego detectado: Game')


if __name__ == '__main__':
    unittest.main()
