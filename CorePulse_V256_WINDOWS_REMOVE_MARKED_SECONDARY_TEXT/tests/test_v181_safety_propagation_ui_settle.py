from pathlib import Path
import hashlib
import unittest

from core.benchmark_telemetry import BenchmarkTelemetry


class SafetyAuditV181Tests(unittest.TestCase):
    def _row(self, ts, distance):
        return {
            'ts': ts, 'boundary': False, 'cpu_usage': 90.0, 'cpu_temp': 99.0,
            'cpu_ghz': 4.0, 'cpu_tjmax_distance': distance, 'ram_usage': 50.0,
            'gpus': [], 'storage': [], 'source_timestamp': ts,
            'throttling': {'cpu': {'state': 'WATCHING', 'evidence': []}, 'gpu': {'devices': []}},
        }

    def test_audit_distinguishes_minimum_from_sustained_trigger(self):
        monitor = BenchmarkTelemetry()
        monitor.rows = [self._row(1.0, 0.0), self._row(1.5, 2.0), self._row(2.0, 1.0)]
        audit = monitor.summary()['thermal_audit']['cpu']['safety_observation']
        self.assertEqual(audit['sample_count_at_or_below'], 2)
        self.assertEqual(audit['max_consecutive_sample_count'], 1)
        self.assertFalse(audit['trigger_observed'])

    def test_audit_marks_three_consecutive_real_samples(self):
        monitor = BenchmarkTelemetry()
        monitor.rows = [self._row(1.0, 1.0), self._row(1.5, 0.5), self._row(2.0, 0.0)]
        audit = monitor.summary()['thermal_audit']['cpu']['safety_observation']
        self.assertEqual(audit['max_consecutive_sample_count'], 3)
        self.assertTrue(audit['trigger_observed'])


class PropagationAndUiV181Tests(unittest.TestCase):
    def test_gpu_runner_receives_combined_should_stop(self):
        text = (Path(__file__).resolve().parents[1] / 'core' / 'benchmark_engine.py').read_text(encoding='utf-8')
        self.assertIn('cancel_check=should_stop', text)

    def test_result_swap_schedules_strong_settle(self):
        text = (Path(__file__).resolve().parents[1] / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
        self.assertIn('def _schedule_visual_benchmark_result_settle', text)
        self.assertIn('self.scroll._refresh_geometry()', text)
        self.assertIn('self.scroll._flush_repaint(strong=True)', text)
        self.assertIn('self._schedule_visual_benchmark_result_settle()', text)

    def test_directx_scene_and_renderer_not_edited_by_ui_patch(self):
        # Guard rail textual: V181 changes orchestration, not scene construction.
        text = (Path(__file__).resolve().parents[1] / 'NOTA_V181.md').read_text(encoding='utf-8')
        self.assertIn('No se retocan agua, vegetación, aviones, shaders ni complejidad visual.', text)

    def test_v13_workload_hashes_match_v180(self):
        root = Path(__file__).resolve().parents[1]
        expected = {
            'core/directx_benchmark.py': '2981c9dda17e691625b6248879b42bcf0816fd594867705f50c41703987a415c',
            'core/directx_scene.py': 'dc6a9225112dd3c8b71daef1dc610427921ea2d92e11f1ee30625342b14e2b0f',
        }
        for rel, digest in expected.items():
            with self.subTest(rel=rel):
                actual = hashlib.sha256((root / rel).read_bytes()).hexdigest()
                self.assertEqual(actual, digest)


if __name__ == '__main__':
    unittest.main()
