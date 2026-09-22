import ast
from pathlib import Path
import unittest

from core.benchmark_telemetry import BenchmarkTelemetry


class ThermalSafetyV180Tests(unittest.TestCase):
    def test_one_degree_tjmax_margin_can_stop_after_three_real_samples(self):
        snapshot = {
            '_cpu': {
                'package_temp_c': 99.0,
                'distance_to_tjmax_min_c': 1.0,
                'usage_percent': 90.0,
                'clock_avg_ghz': 4.0,
            },
            '_gpus': [], '_storage_devices': [], 'ram_usage': 50.0,
        }
        monitor = BenchmarkTelemetry(lambda: snapshot)
        monitor.sample(force=True)
        self.assertIsNone(monitor.stop_reason)
        monitor.sample(force=True)
        self.assertIsNone(monitor.stop_reason)
        monitor.sample(force=True)
        self.assertIn('CPU permaneció a 1.0 °C o menos de TjMax', monitor.stop_reason or '')

    def test_above_one_degree_resets_sustained_counter(self):
        snapshot = {
            '_cpu': {'package_temp_c': 99.0, 'distance_to_tjmax_min_c': 1.0},
            '_gpus': [], '_storage_devices': [], 'ram_usage': 50.0,
        }
        monitor = BenchmarkTelemetry(lambda: snapshot)
        monitor.sample(force=True)
        monitor.sample(force=True)
        snapshot['_cpu']['distance_to_tjmax_min_c'] = 1.5
        monitor.sample(force=True)
        snapshot['_cpu']['distance_to_tjmax_min_c'] = 1.0
        monitor.sample(force=True)
        self.assertIsNone(monitor.stop_reason)


class AtomicUiV180Tests(unittest.TestCase):
    def test_benchmark_async_does_not_request_full_canvas_render(self):
        source = Path(__file__).resolve().parents[1] / 'gui' / 'health_center_panel.py'
        text = source.read_text(encoding='utf-8')
        self.assertIn("name != 'visual_benchmark'", text)
        self.assertIn('self._refresh_visual_benchmark_result_in_place()', text)

    def test_result_host_is_created_before_result_body(self):
        source = Path(__file__).resolve().parents[1] / 'gui' / 'health_center_panel.py'
        text = source.read_text(encoding='utf-8')
        create = text.index('self._visual_benchmark_result_host = ctk.CTkFrame')
        render = text.index('self._render_visual_benchmark_result_body(self._visual_benchmark_result_host, result)')
        self.assertLess(create, render)

    def test_directx_workload_modules_not_referenced_by_v180_patch(self):
        source = Path(__file__).resolve().parents[1] / 'gui' / 'health_center_panel.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        self.assertNotIn('run_directx_benchmark', names)


if __name__ == '__main__':
    unittest.main()
