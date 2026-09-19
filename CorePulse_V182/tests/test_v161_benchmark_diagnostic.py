"""Pruebas del flujo real con proveedores/cargas instrumentados; sin cambiar Windows."""
import copy
import hashlib
import json
from contextlib import ExitStack
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

from core import benchmark_engine as bench, complete_diagnostic as diag
from core.benchmark_telemetry import BenchmarkTelemetry
from core.diagnostic_lifecycle import is_completed_benchmark, is_finalized_result
from core.diagnostic_summary import build_component_assessments, build_component_evidence, select_priority_assessment
from tests.test_v157_diagnostic_lifecycle import app_harness

ROOT = Path(__file__).resolve().parents[1]


def baseline():
    return {'session_valid': True, 'sample_count': 30, 'duration_seconds': 30,
            'overall_status': 'NORMAL', 'findings': [], 'statistics': {
                'cpu': {'usage_percent': {'avg': 8}, 'package_temp_c': {'avg': 42}},
                'ram': {'usage_percent': {'avg': 30}}}}


class Rig:
    def __init__(self, cancel=None, hot=None, error=None):
        self.cancel = cancel
        self.hot = hot
        self.error = error
        self.event = threading.Event()
        self.active = None
        self.calls = []
        self.clock = 0

    def tick(self):
        self.clock += .5
        return self.clock

    def sample(self):
        return {'cpu_usage': 100 if self.active == 'cpu' else 12,
                'cpu_temp': 97 if self.hot and self.active == self.hot else 79 if self.active == 'cpu' else 45,
                'cpu_ghz': 4.1, 'ram_usage': 62 if self.active == 'ram' else 30,
                '_gpus': [{'name': 'GPU Test', 'usage_percent': 99, 'temperature_c': 71, 'core_clock_mhz': 1800},
                          {'name': 'Other GPU', 'usage_percent': 0, 'temperature_c': 40, 'core_clock_mhz': 300}],
                '_storage_devices': [{'name': 'Drive Test', 'temperature_c': 53 if self.active == 'ssd' else 35,
                                      'mount_points': ['C:\\'], 'windows_health_status': 'Healthy'}]}

    def workload(self, key):
        def execute(*args, **kwargs):
            self.calls.append(key)
            self.active = key
            for index in range(2):
                kwargs['progress_callback'](index / 2, key.upper(), 'medición instrumentada')
                if self.cancel == key:
                    self.event.set()
                if kwargs['stop_check']():
                    break
            if self.error == key:
                raise RuntimeError('error de medición controlado')
            return {'kind': key.upper(), 'status': 'OK', 'value': 5120, 'unit': 'MB/s', 'duration_s': 2,
                    'throughput_mbps': 5120, 'renderer': 'GPU Test' if key == 'gpu' else None,
                    'frames_per_s': 41, 'fps_1pct_low': 29, 'read_mbps': 1200, 'write_mbps': 800,
                    'path_root': 'C:\\' if key == 'ssd' else None}
        return execute

    def __enter__(self):
        self.stack = ExitStack()
        for key in ('cpu', 'ram', 'ssd', 'gpu'):
            self.stack.enter_context(patch.object(bench, 'benchmark_' + key, self.workload(key)))
        self.stack.enter_context(patch('core.benchmark_telemetry.time', types.SimpleNamespace(monotonic=self.tick, time=time.time)))
        for name in ('analyze_startup', 'analyze_services', 'analyze_crashes', 'analyze_drivers'):
            self.stack.enter_context(patch.object(diag, name, return_value={'count': 0, 'items': [], 'severity': 'NORMAL', 'device_problems': 0}))
        self.stack.enter_context(patch.object(diag, 'collect_battery_health', return_value={'present': False}))
        self.stress = self.stack.enter_context(patch.object(diag, 'run_stress_suite', side_effect=AssertionError('estrés automático prohibido')))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def run(self, **kwargs):
        return diag.run_complete_diagnostic(baseline(), self.sample(), [], telemetry_sampler=self.sample,
                                             cancel_check=self.event.is_set, **kwargs)


class FlowTests(unittest.TestCase):
    def test_only_benchmark_runs_and_coverage_has_real_phases(self):
        with Rig() as rig:
            states = []
            result = rig.run(state_callback=states.append)
            rig.stress.assert_not_called()
        self.assertEqual(rig.calls, ['cpu', 'ram', 'ssd', 'gpu'])
        block = result['complete_diagnostic']
        self.assertEqual(block['status'], 'COMPLETE')
        self.assertEqual(list(block['phases']), ['desktop', 'hardware', 'windows', 'benchmark', 'load_observation', 'correlation'])
        self.assertEqual(block['phase_coverage'], {'completed': 6, 'total': 6, 'partial': False})
        self.assertNotIn('stress_test', block)
        self.assertEqual(states, ['RUNNING_HARDWARE', 'RUNNING_WINDOWS', 'RUNNING_BENCHMARK', 'ANALYZING_BENCHMARK', 'CORRELATING'])

    def test_component_telemetry_and_metrics_preserved(self):
        with Rig() as rig:
            result = rig.run()
        b = result['complete_diagnostic']['benchmark']
        self.assertEqual(b['cpu']['telemetry']['cpu_temp']['max'], 79)
        self.assertEqual(b['ram']['telemetry']['cpu_temp']['max'], 45)
        self.assertEqual(b['ram']['telemetry']['ram_usage']['max'], 62)
        self.assertEqual(b['gpu']['telemetry']['gpu_temp']['max'], 71)
        self.assertEqual(b['telemetry_summary']['gpu_temp']['max'], 71)
        self.assertEqual(b['ssd']['telemetry']['storage_temperature']['max'], 53)
        self.assertEqual(b['ssd']['telemetry']['storage_temperature']['initial'], 35)
        self.assertEqual(b['cpu']['throughput_mbps'], 5120)
        self.assertEqual(b['gpu']['fps_1pct_low'], 29)
        self.assertEqual(b['ssd']['read_mbps'], 1200)
        self.assertTrue(is_completed_benchmark(b))

    def test_cancel_each_benchmark_then_restart_clean(self):
        keys = ['cpu', 'ram', 'ssd', 'gpu']
        for key in keys:
            with self.subTest(key=key), Rig(cancel=key) as rig:
                cancelled = rig.run()
                self.assertEqual(rig.calls, keys[:keys.index(key) + 1])
                self.assertFalse(is_finalized_result(cancelled))
                self.assertFalse(is_completed_benchmark(cancelled['complete_diagnostic']['benchmark']))
                self.assertEqual(cancelled['complete_diagnostic']['status'], 'CANCELLED')
                self.assertFalse(cancelled['complete_diagnostic']['pdf_optional'])
                rig.event.clear()
                rig.cancel = None
                rig.calls.clear()
                rerun = rig.run()
                self.assertTrue(is_finalized_result(rerun))
                self.assertTrue(is_completed_benchmark(rerun['complete_diagnostic']['benchmark']))
                self.assertEqual(rig.calls, keys)

    def test_thermal_stop_preserves_evidence_and_skips_later_load(self):
        with Rig(hot='cpu') as rig:
            result = rig.run()
        b = result['complete_diagnostic']['benchmark']
        self.assertEqual(rig.calls, ['cpu'])
        self.assertEqual(b['cpu']['status'], 'SAFETY_STOP')
        self.assertEqual(b['cpu']['telemetry']['cpu_temp']['max'], 97)
        self.assertFalse(is_completed_benchmark(b))
        self.assertEqual(result['complete_diagnostic']['status'], 'PARTIAL')
        priority = select_priority_assessment(build_component_assessments(result))
        self.assertEqual(priority['key'], 'cpu')
        self.assertIn('97.0', str(result['findings']))
        for key in ('ram', 'ssd', 'gpu'):
            self.assertEqual(b[key]['status'], 'SKIPPED')
        for card in build_component_assessments(result):
            if card['key'] in {'ram', 'gpu'}:
                self.assertEqual(card['status'], 'NO_EVALUABLE')

    def test_measurement_exception_keeps_prior_evidence_and_is_not_hardware_failure(self):
        with Rig(error='ram') as rig:
            result = rig.run()
        b = result['complete_diagnostic']['benchmark']
        self.assertEqual(b['cpu']['status'], 'OK')
        self.assertEqual(b['ram']['status'], 'ERROR')
        self.assertIn('controlado', str(b['ram']['telemetry']['execution_errors']))
        self.assertFalse(is_completed_benchmark(b))
        self.assertIsNone(select_priority_assessment(build_component_assessments(result)))

    def test_missing_sensors_stay_na_and_benchmark_can_complete(self):
        with Rig() as rig:
            result = diag.run_complete_diagnostic(baseline(), {}, [], telemetry_sampler=lambda: {})
        b = result['complete_diagnostic']['benchmark']
        self.assertTrue(is_completed_benchmark(b))
        self.assertEqual(result['complete_diagnostic']['load_observation']['status'], 'PARTIAL')
        for item in build_component_assessments(result)[:3]:
            self.assertEqual(item['facets'][-1][1], 'N/A')
        self.assertIsNone(select_priority_assessment(build_component_assessments(result)))

    def test_history_records_finished_benchmark_exactly_once(self):
        with Rig() as rig:
            result = rig.run()
        app = app_harness()
        with patch('gui.diagnostic_view.show_diagnostic_experience', return_value=app.diagnostic_experience_panel), \
             patch('core.diagnostic_history.load_previous_complete_result', return_value=None), \
             patch('core.diagnostic_history.build_diagnostic_comparison', return_value={}), \
             patch('core.diagnostic_pipeline.integrate_current_diagnostic_pipeline', return_value={}), \
             patch.object(diag, 'save_complete_result', return_value='test.json'):
            app.start_diagnostic_session()
            app.diagnostic_session.finish({})
            app._complete_diagnostic_running = True
            token = app._diagnostic_run_token
            app._complete_diagnostic_finished(result, run_token=token)
            app._complete_diagnostic_finished(result, run_token=token)
        app.health_history_store.record_benchmark_session.assert_called_once()


class TelemetryTests(unittest.TestCase):
    def test_gpu_identity_and_throttling_do_not_mix_devices(self):
        sample = Rig().sample()
        sample['_gpus'][1]['sensors'] = [{'name': 'Thermal throttling', 'value': 1}]
        monitor = BenchmarkTelemetry(lambda: sample)
        monitor.sample(force=True)
        matched = monitor.summary('GPU Test')
        self.assertEqual(matched['gpu_temp']['max'], 71)
        self.assertEqual(matched['throttling']['gpu']['state'], 'NO_EVIDENCE')
        unknown = monitor.summary('Unknown renderer')
        self.assertIsNone(unknown['gpu_temp']['max'])
        self.assertEqual(unknown['throttling']['gpu']['state'], 'N/A')

    def test_storage_mapping_uses_live_temperature_not_cached_health(self):
        sample = {'_storage_devices': [{'name': 'Drive', 'temperature_c': 52}]}
        inventory = [{'model': 'Drive', 'mount_points': 'C:; D:', 'temperature_c': 10}]
        monitor = BenchmarkTelemetry(lambda: sample, inventory)
        monitor.sample(force=True)
        self.assertEqual(monitor.summary(path_root='C:\\')['storage_temperature']['max'], 52)
        self.assertIsNone(monitor.summary(path_root='Z:\\')['storage_temperature']['max'])
        monitor = BenchmarkTelemetry(lambda: sample, inventory * 2)
        monitor.sample(force=True)
        self.assertIsNone(monitor.summary(path_root='C:\\')['storage_temperature']['max'])

    def test_explicit_throttling_and_watching_are_distinct(self):
        for explicit, expected in ((False, 'WATCHING'), (True, 'CONFIRMED')):
            sample = {'cpu_temp': 94, 'cpu_usage': 100, 'cpu_ghz': 4,
                      '_cpu': {'sensors': [{'name': 'Thermal throttling', 'value': 1}] if explicit else []}}
            monitor = BenchmarkTelemetry(lambda: sample)
            monitor.sample(force=True)
            telemetry = monitor.summary()
            self.assertEqual(telemetry['throttling']['cpu']['state'], expected)
            findings = diag._complete_findings({}, {}, {}, {'cpu': {'status': 'OK', 'telemetry': telemetry}})
            self.assertIn('94.0', str(findings))
            if not explicit:
                self.assertIn('No se confirmó throttling', str(findings))

    def test_sensor_error_is_na_not_success_or_hardware_error(self):
        monitor = BenchmarkTelemetry(Mock(side_effect=RuntimeError('sensor offline')))
        monitor.sample(force=True)
        summary = monitor.summary()
        self.assertEqual(summary['sample_count'], 0)
        self.assertEqual(summary['throttling']['cpu']['state'], 'N/A')
        self.assertIn('sensor offline', str(summary['sampler_errors']))
        self.assertIsNone(monitor.stop_reason)

    def test_gpu_thermal_limit_remains_92_even_without_renderer(self):
        monitor = BenchmarkTelemetry(lambda: {'_gpus': [{'name': 'GPU', 'temperature_c': 92}]})
        monitor.sample(force=True)
        self.assertIn('GPU alcanzó 92.0', monitor.stop_reason)


class PresentationTests(unittest.TestCase):
    def test_running_phase_markers_follow_worker_state(self):
        from gui.diagnostic_view import _running_phase_values, _phase_statuses
        from core.diagnostic_lifecycle import DiagnosticState
        self.assertEqual(_running_phase_values(DiagnosticState.RUNNING_BENCHMARK), ['✓', '✓', '●', '●'])
        self.assertEqual(_running_phase_values(DiagnosticState.ANALYZING_BENCHMARK), ['✓', '✓', '✓', '●'])
        with Rig(hot='cpu') as rig:
            result = rig.run()
        self.assertEqual(dict(_phase_statuses(result))['Benchmark'], 'SAFETY_STOP')

    def test_shared_evidence_and_facets_use_benchmark_load(self):
        with Rig() as rig:
            result = rig.run()
        for key in ('cpu', 'gpu', 'ram'):
            card = next(r for r in build_component_assessments(result) if r['key'] == key)
            self.assertEqual([f[0] for f in card['facets']], ['Escritorio', 'Benchmark', 'Bajo carga'])
            evidence = build_component_evidence(result, key)
            self.assertEqual([s['title'] for s in evidence['sections']], ['Escritorio', 'Benchmark', 'Telemetría durante benchmark'])
            self.assertNotIn('estrés', json.dumps(evidence, ensure_ascii=False).lower())
        self.assertIn('53.0 °C', str(build_component_evidence(result, 'storage')))

    def test_pdf_uses_same_evidence_without_stress_and_keeps_all_rows(self):
        from core.report_builder import _complete_diagnostic_flowables, _styles
        with Rig() as rig:
            result = rig.run()
        text = []
        def visit(value):
            if isinstance(value, (list, tuple)):
                for item in value:
                    visit(item)
            elif hasattr(value, 'getPlainText'):
                text.append(value.getPlainText())
            elif hasattr(value, '_cellvalues'):
                visit(value._cellvalues)
            elif isinstance(value, str):
                text.append(value)
        visit(_complete_diagnostic_flowables(result, _styles()))
        output = ' '.join(text)
        self.assertNotIn('estrés', output.lower())
        self.assertIn('Telemetría durante benchmark', output)
        for key in ('cpu', 'gpu', 'ram', 'storage'):
            for section in build_component_evidence(result, key)['sections']:
                for row in section['rows']:
                    self.assertIn(row['value'], output)

    def test_cancelled_result_rejected_by_pdf_builder(self):
        from core.report_builder import build_pdf_report
        with Rig(cancel='cpu') as rig:
            result = rig.run()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'invalid.pdf'
            with self.assertRaises(ValueError):
                build_pdf_report({}, [], None, path, result, {})
            self.assertFalse(path.exists())

    def test_protected_files_match_v160_hashes(self):
        hashes = json.loads((ROOT / 'PROTEGIDOS_V160_SHA256.json').read_text(encoding='utf-8'))
        self.assertEqual(len(hashes), 5)
        for name, expected in hashes.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)


if __name__ == '__main__':
    unittest.main()

