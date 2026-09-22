import ast
from pathlib import Path
import unittest

from core.benchmark_telemetry import BenchmarkTelemetry
from tests.test_v177_benchmark_ui import Widget, panel_class


def _gpu(temp, *, limit=93.0, hotspot=None, hotspot_limit=None):
    sensors = [
        {'name': 'GPU Core Temperature Limit', 'type': 'Temperature', 'value': limit},
    ]
    if hotspot_limit is not None:
        sensors.append({'name': 'GPU Hot Spot Temperature Limit', 'type': 'Temperature', 'value': hotspot_limit})
    return {
        'name': 'NVIDIA GeForce RTX 2070',
        'temperature_c': temp,
        'hotspot_c': hotspot,
        'usage_percent': 99.0,
        'core_clock_mhz': 1600.0,
        'sensors': sensors,
    }


def _row(ts, cpu_temp, cpu_distance, gpu_temp, *, hotspot=None):
    return {
        'ts': ts,
        'boundary': False,
        'cpu_usage': 85.0,
        'cpu_temp': cpu_temp,
        'cpu_ghz': 4.0,
        'cpu_tjmax_distance': cpu_distance,
        'ram_usage': 60.0,
        'gpus': [_gpu(gpu_temp, hotspot=hotspot, hotspot_limit=105.0)],
        'storage': [],
        'source_timestamp': ts,
        'throttling': {
            'cpu': {'state': 'WATCHING', 'evidence': []},
            'gpu': {'devices': [{'name': 'NVIDIA GeForce RTX 2070', 'state': 'WATCHING', 'evidence': []}]},
        },
    }


class ThermalAuditTests(unittest.TestCase):
    def test_real_samples_expose_peak_streak_and_real_limits(self):
        monitor = BenchmarkTelemetry()
        monitor.rows = [
            _row(1000.0, 94.0, 6.0, 87.0, hotspot=96.0),
            _row(1000.5, 100.0, 1.0, 89.0, hotspot=99.0),
            _row(1001.0, 99.0, 1.5, 90.0, hotspot=100.0),
            _row(1001.5, 92.0, 8.0, 86.0, hotspot=95.0),
        ]
        summary = monitor.summary('NVIDIA GeForce RTX 2070')
        audit = summary['thermal_audit']
        self.assertEqual(audit['policy'], 'REAL_OR_NA_OBSERVED_SAMPLES_ONLY')
        self.assertEqual(audit['cpu']['peak_c'], 100.0)
        self.assertEqual(audit['cpu']['warning_observation']['sample_count_at_or_above'], 2)
        self.assertEqual(audit['cpu']['warning_observation']['max_consecutive_observed_span_s'], 0.5)
        self.assertEqual(audit['cpu']['minimum_tjmax_distance_c'], 1.0)
        self.assertEqual(audit['cpu']['safety_authority'], 'REAL_TJMAX_DISTANCE')
        self.assertEqual(audit['gpu']['peak_c'], 90.0)
        self.assertEqual(audit['gpu']['warning_observation']['sample_count_at_or_above'], 2)
        self.assertEqual(audit['gpu']['reported_core_temp_limit_c'], 93.0)
        self.assertEqual(audit['gpu']['minimum_margin_to_reported_core_limit_c'], 3.0)
        self.assertEqual(audit['gpu']['reported_hotspot_limit_c'], 105.0)
        self.assertEqual(audit['gpu']['minimum_margin_to_reported_hotspot_limit_c'], 5.0)


    def test_zero_tjmax_distance_is_preserved_and_can_stop(self):
        snapshots = [{
            '_cpu': {'package_temp_c': 100.0, 'distance_to_tjmax_min_c': 0.0, 'usage_percent': 90.0, 'clock_avg_ghz': 4.0},
            '_gpus': [], '_storage_devices': [], 'ram_usage': 50.0,
        }]
        monitor = BenchmarkTelemetry(lambda: snapshots[0])
        monitor.sample(force=True)
        monitor.sample(force=True)
        monitor.sample(force=True)
        self.assertEqual(monitor.rows[-1]['cpu_tjmax_distance'], 0.0)
        self.assertIn('CPU permaneció a 0.0 °C o menos de TjMax', monitor.stop_reason or '')

    def test_reported_gpu_limit_can_trigger_sustained_stop_below_fallback(self):
        snapshot = {
            '_cpu': {}, '_storage_devices': [], 'ram_usage': 50.0,
            '_gpus': [_gpu(89.0, limit=88.0, hotspot=95.0, hotspot_limit=105.0)],
            'gpu_temp': 89.0,
        }
        monitor = BenchmarkTelemetry(lambda: snapshot)
        monitor.sample(force=True)
        monitor.sample(force=True)
        monitor.sample(force=True)
        self.assertIn('límite reportado (89.0/88.0 °C)', monitor.stop_reason or '')

    def test_missing_limits_remain_na(self):
        monitor = BenchmarkTelemetry()
        row = _row(2000.0, 90.0, None, 80.0)
        row['gpus'][0]['sensors'] = []
        monitor.rows = [row]
        audit = monitor.summary('NVIDIA GeForce RTX 2070')['thermal_audit']
        self.assertIsNone(audit['cpu']['minimum_tjmax_distance_c'])
        self.assertEqual(audit['cpu']['safety_authority'], 'ABSOLUTE_FALLBACK_105C_NO_TJMAX')
        self.assertIsNone(audit['gpu']['reported_core_temp_limit_c'])
        self.assertIsNone(audit['gpu']['minimum_margin_to_reported_core_limit_c'])


class BenchmarkUiClosureTests(unittest.TestCase):
    def test_partial_progress_never_renders_listo(self):
        Widget.created = []
        panel = panel_class()()
        panel._alive = True
        panel._jobs = set()  # reproduce la ventana transitoria observada
        panel._visual_bench = None
        panel._visual_benchmark_run_id = 7
        panel._visual_benchmark_progress = 0.97
        panel._visual_benchmark_stage = 'Finalizando GPU'
        panel._visual_benchmark_detail = 'Cerrando DirectX'
        panel.visual_bench_progress_bar = None
        panel.lbl_visual_bench_progress = None
        panel.lbl_visual_bench_detail = None
        panel._render_visual_benchmark_card(None)
        texts = [w.options.get('text') for w in Widget.created]
        self.assertIn('EN EJECUCIÓN', texts)
        self.assertNotIn('LISTO', texts)
        self.assertTrue(any(isinstance(t, str) and t.startswith('97% ·') for t in texts))

    def test_benchmark_done_does_not_force_second_immediate_render(self):
        source = Path(__file__).resolve().parents[1] / 'gui' / 'health_center_panel.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'HealthCenterPanel')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_run_visual_benchmark')
        calls = [
            n for n in ast.walk(method)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name) and n.func.value.id == 'self'
            and n.func.attr == '_render'
        ]
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
