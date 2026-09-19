"""Regresiones ejecutables, sin modificar Windows ni depender de sensores reales.

python -m unittest tests.test_v157_diagnostic_lifecycle -v
"""
import ast
import copy
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

from core.adaptive_diagnostic import AdaptiveDiagnosticSession
from core.diagnostic_lifecycle import DiagnosticRun, DiagnosticState, is_finalized_result, is_completed_benchmark
from core import complete_diagnostic as engine
from core import benchmark_engine as bench
from core.diagnostic_summary import build_component_evidence, build_component_assessments, select_priority_assessment
from core.diagnostic_evidence import active_gpu, storage_snapshot

ROOT = Path(__file__).resolve().parents[1]


def final_result():
    return {'session_valid': True, 'sample_count': 30, 'duration_seconds': 30,
            'overall_status': 'NORMAL', 'statistics': {}, 'findings': [],
            'complete_diagnostic': {'finalized': True, 'status': 'COMPLETE',
                'hardware': {'battery': {'present': False}}, 'windows': {},
                'stress_test': {}, 'benchmark': {}, 'phase_coverage': {'completed': 7, 'total': 7}}}


class Widget:
    def __init__(self):
        self.values = {}
    def configure(self, **kwargs):
        self.values.update(kwargs)


def app_harness():
    """Ejecuta métodos reales de main sin iniciar bandeja, sensores ni servicios."""
    tree = ast.parse((ROOT / 'main.py').read_text(encoding='utf-8'))
    names = {'start_diagnostic_session', 'cancel_diagnostic_session', '_stop_diagnostic_callbacks',
             '_prepare_diagnostic_run', '_poll_diagnostic_worker', '_update_diagnostic_countdown',
             '_finish_diagnostic_session', '_apply_complete_diagnostic_progress', '_complete_diagnostic_finished'}
    app_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and any(getattr(x, 'name', '') == 'start_diagnostic_session' for x in n.body))
    methods = [n for n in app_node.body if isinstance(n, ast.FunctionDef) and n.name in names]
    cls = ast.ClassDef(name='Harness', bases=[], keywords=[], body=methods, decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    namespace = dict(time=time, copy=copy, threading=threading, DiagnosticRun=DiagnosticRun,
                     DiagnosticState=DiagnosticState, is_finalized_result=is_finalized_result,
                     is_completed_benchmark=is_completed_benchmark, theme_color=lambda x: x,
                     refresh_navigation_state=lambda a: None, cp_info=lambda *a: None, cp_warning=lambda *a: None,
                     logger=logging.getLogger('test'), VERSION_LABEL='V157', data_path=lambda x: x)
    exec(compile(module, str(ROOT / 'main.py'), 'exec'), namespace)
    app = namespace['Harness']()
    app.is_running = app._services_ready = True
    app.diagnostic_session = AdaptiveDiagnosticSession()
    app.realtime_agent = Mock(get_state=Mock(return_value={}))
    app.latest_telemetry = {'cpu_usage': 10, 'ram_usage': 40}
    app.latest_disks = []
    app.latest_score = None
    app.telemetry_lock = threading.RLock()
    app.diagnostic_result = None
    app._complete_diagnostic_running = False
    app._diagnostic_run_token = 0
    app._diagnostic_run = app._diagnostic_worker = None
    app._diagnostic_poll_id = app.diagnostic_after_id = None
    app._diagnostic_cancel_event = threading.Event()
    app.btn_pdf = Widget()
    app.btn_diagnostic = Widget()
    app.diagnostic_experience_panel = Mock()
    app.diagnostic_experience_panel.winfo_exists.return_value = True
    app.diagnostic_experience_panel.winfo_viewable.return_value = True
    app.session_trend_collector = None
    app.health_history_store = Mock()
    app.callbacks = {}
    app._callback_seq = 0
    def after(ms, fn):
        app._callback_seq += 1
        app.callbacks[app._callback_seq] = fn
        return app._callback_seq
    app.after = after
    app.after_cancel = lambda key: app.callbacks.pop(key, None)
    return app


class LifecycleTests(unittest.TestCase):
    def test_cancel_idempotent_and_late_messages_rejected(self):
        run = DiagnosticRun(1)
        run.transition(DiagnosticState.RUNNING_STRESS_CPU)
        run.post_progress(.5, 'CPU')
        self.assertTrue(run.cancel())
        self.assertFalse(run.cancel())
        run.post_result(final_result())
        run.post_progress(1, 'Completado')
        self.assertEqual(run.drain(), (None, None))
        self.assertFalse(run.transition(DiagnosticState.COMPLETED))
        newer = DiagnosticRun(2)
        self.assertFalse(newer.cancel_event.is_set())

    def test_progress_coalesces_and_state_cannot_move_backwards(self):
        run = DiagnosticRun(1)
        run.transition(DiagnosticState.RUNNING_BENCHMARK)
        self.assertFalse(run.transition(DiagnosticState.RUNNING_BASELINE))
        for i in range(10000):
            run.post_progress(i / 10000, 'RAM')
        self.assertEqual(run.drain()[0][0], .9999)

    def test_cancel_restart_all_stages_and_stale_callback(self):
        for phase in (DiagnosticState.RUNNING_BASELINE, DiagnosticState.RUNNING_WINDOWS,
                      DiagnosticState.RUNNING_STRESS_CPU, DiagnosticState.RUNNING_STRESS_RAM,
                      DiagnosticState.RUNNING_STRESS_GPU, DiagnosticState.RUNNING_BENCHMARK):
            with self.subTest(phase=phase):
                app = app_harness()
                with patch('gui.diagnostic_view.show_diagnostic_experience', return_value=app.diagnostic_experience_panel):
                    app.start_diagnostic_session()
                    old_token = app._diagnostic_run_token
                    old = app._diagnostic_run
                    old.transition(phase)
                    app._complete_diagnostic_running = phase != DiagnosticState.RUNNING_BASELINE
                    app.cancel_diagnostic_session()
                    app.cancel_diagnostic_session()
                    self.assertFalse(app.diagnostic_session.active)
                    self.assertFalse(app._complete_diagnostic_running)
                    self.assertTrue(old.cancel_event.is_set())
                    self.assertFalse(app.callbacks)
                    self.assertIsNone(app.diagnostic_result)
                    app.start_diagnostic_session()
                    self.assertTrue(app.diagnostic_session.active)
                    self.assertFalse(app._diagnostic_cancel_event.is_set())
                    app._complete_diagnostic_finished(final_result(), run_token=old_token)
                    app._apply_complete_diagnostic_progress(.95, 'Viejo', run_token=old_token)
                    self.assertIsNone(app.diagnostic_result)
                    self.assertEqual(app._complete_diagnostic_stage, 'Estado en escritorio')
                    self.assertEqual(app.btn_pdf.values['state'], 'disabled')

    def test_restart_waits_for_old_load_before_sampling(self):
        app = app_harness()
        release = threading.Event()
        worker = threading.Thread(target=lambda: release.wait(3))
        worker.start()
        app._diagnostic_worker = worker
        try:
            with patch('gui.diagnostic_view.show_diagnostic_experience', return_value=app.diagnostic_experience_panel):
                app.start_diagnostic_session()
                self.assertFalse(app.diagnostic_session.active)
                self.assertEqual(app._diagnostic_run.state, DiagnosticState.PREPARING)
                release.set()
                worker.join(1)
                app._prepare_diagnostic_run(app._diagnostic_run_token)
                self.assertTrue(app.diagnostic_session.active)
        finally:
            release.set()
            worker.join(1)

    def test_complete_after_cancel_saves_once_and_no_cancelled_benchmark(self):
        app = app_harness()
        history = types.ModuleType('core.diagnostic_history')
        history.load_previous_complete_result = lambda: None
        history.build_diagnostic_comparison = lambda *a: {'available': False}
        pipeline = types.ModuleType('core.diagnostic_pipeline')
        pipeline.integrate_current_diagnostic_pipeline = Mock(return_value={})
        with patch('gui.diagnostic_view.show_diagnostic_experience', return_value=app.diagnostic_experience_panel), \
             patch.dict(sys.modules, {'core.diagnostic_history': history, 'core.diagnostic_pipeline': pipeline}), \
             patch.object(engine, 'save_complete_result', return_value='result.json') as save:
            app.start_diagnostic_session()
            app.cancel_diagnostic_session()
            app.start_diagnostic_session()
            app.diagnostic_session.finish({})
            app._complete_diagnostic_running = True
            result = final_result()
            result['complete_diagnostic']['benchmark'] = {'status': 'CANCELLED', 'cancelled': True}
            token = app._diagnostic_run_token
            app._complete_diagnostic_finished(result, run_token=token)
            app._complete_diagnostic_finished(result, run_token=token)
            save.assert_called_once()
            app.health_history_store.record_benchmark_session.assert_not_called()
            self.assertEqual(app._diagnostic_run.state, DiagnosticState.COMPLETED)
            self.assertEqual(app.btn_pdf.values['state'], 'normal')

    def test_cancelled_and_error_results_cannot_enable_pdf_or_save(self):
        for status in ('CANCELLED', 'ERROR'):
            with self.subTest(status=status):
                app = app_harness()
                with patch('gui.diagnostic_view.show_diagnostic_experience', return_value=app.diagnostic_experience_panel), \
                     patch.object(engine, 'save_complete_result') as save:
                    app.start_diagnostic_session()
                    app._complete_diagnostic_running = True
                    result = final_result()
                    result['complete_diagnostic'].update(status=status, finalized=False)
                    app._complete_diagnostic_finished(result, run_token=app._diagnostic_run_token)
                    save.assert_not_called()
                    self.assertIsNone(app.diagnostic_result)
                    self.assertEqual(app.btn_pdf.values['state'], 'disabled')


class EngineTests(unittest.TestCase):
    def test_stress_cancel_each_component(self):
        for target in ('cpu', 'ram', 'gpu'):
            with self.subTest(target=target):
                event = threading.Event()
                calls = []
                def load(key):
                    def run(*a, **kw):
                        calls.append(key)
                        if key == target:
                            event.set()
                        return {'status': 'OK', 'duration_s': .1, 'working_set_mb': 64}
                    return run
                with patch.object(engine, '_cpu_stress', load('cpu')), patch.object(engine, '_ram_stress', load('ram')), patch.object(engine, 'benchmark_gpu', load('gpu')):
                    result = engine.run_stress_suite(cancel_check=event.is_set)
                self.assertEqual(result['status'], 'CANCELLED')
                self.assertEqual(calls[-1], target)
                self.assertEqual(result['components'][target]['status'], 'CANCELLED')

    def test_real_cpu_cancel_joins_hash_workers(self):
        event = threading.Event()
        started = time.monotonic()
        result = bench.benchmark_cpu(3, threads=2, progress_callback=lambda f, s, d: event.set() if 'multinúcleo' in s else None, stop_check=event.is_set)
        self.assertEqual(result['status'], 'SAFETY_STOP')
        self.assertLess(time.monotonic() - started, 2)
        self.assertFalse(any(t.name.startswith('CorePulse-BenchCPU') for t in threading.enumerate()))

    def test_real_stress_cpu_exception_stops_workers(self):
        with patch.object(engine, 'os') as os_mock:
            os_mock.cpu_count.return_value = 2
            with self.assertRaises(RuntimeError):
                engine._cpu_stress(3, engine._StressMonitor(None), cancel_check=Mock(side_effect=RuntimeError('observer failed')))
        self.assertFalse(any(t.name.startswith('CorePulse-StressCPU') for t in threading.enumerate()))

    def test_real_ram_cancel_and_ssd_partial_bytes(self):
        event = threading.Event()
        ram = bench.benchmark_ram(32, min_seconds=3, progress_callback=lambda *a: event.set(), stop_check=event.is_set)
        self.assertEqual(ram['status'], 'SAFETY_STOP')
        event.clear()
        with tempfile.TemporaryDirectory() as tmp:
            ssd = bench.benchmark_ssd(tmp, 64, progress_callback=lambda *a: event.set(), stop_check=event.is_set)
            self.assertEqual(ssd['status'], 'SAFETY_STOP')
            self.assertEqual(ssd['size_mb'], 4)
            self.assertFalse(list(Path(tmp).iterdir()))

    def test_benchmark_cancel_does_not_measure_later_components(self):
        event = threading.Event()
        def cpu(*a, **kw):
            event.set()
            return {'status': 'SAFETY_STOP'}
        with patch.object(bench, 'benchmark_cpu', cpu), patch.object(bench, 'benchmark_ram') as ram:
            result = bench.run_benchmark_suite(cancel_check=event.is_set)
        self.assertEqual(result['status'], 'CANCELLED')
        self.assertEqual(result['cpu']['status'], 'CANCELLED')
        ram.assert_not_called()
        self.assertFalse(is_completed_benchmark(result))

    def test_process_cancel_kills_owned_child(self):
        from core.cancellable_process import cancellation_scope, run, DiagnosticCancelled
        event = threading.Event()
        timer = threading.Timer(.25, event.set)
        timer.start()
        started = time.monotonic()
        try:
            with cancellation_scope(event.is_set), self.assertRaises(DiagnosticCancelled):
                run([sys.executable, '-c', 'import time; time.sleep(15)'], capture_output=True, timeout=20,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        finally:
            timer.cancel()
        self.assertLess(time.monotonic() - started, 3)

    def test_cancel_at_correlation_and_thermal_stop(self):
        event = threading.Event()
        base = final_result()
        base.pop('complete_diagnostic')
        windows = {'count': 0, 'items': [], 'severity': 'NORMAL', 'device_problems': 0}
        stress = {'status': 'OK', 'components': {}}
        benchmark = {'status': 'OK', **{key: {'status': 'OK'} for key in ('cpu', 'ram', 'ssd', 'gpu')}}
        with patch.object(engine, 'collect_battery_health', return_value={'present': False}), \
             patch.object(engine, 'analyze_startup', return_value=windows), patch.object(engine, 'analyze_services', return_value=windows), \
             patch.object(engine, 'analyze_crashes', return_value=windows), patch.object(engine, 'analyze_drivers', return_value=windows), \
             patch.object(engine, 'run_stress_suite', return_value=stress), patch.object(engine, 'run_benchmark_suite', return_value=benchmark) as workload, \
             patch.object(engine.time, 'sleep', return_value=None):
            result = engine.run_complete_diagnostic(base, {}, [], cancel_check=event.is_set,
                progress_callback=lambda f, s, d: event.set() if s == 'Correlacionando evidencia' else None)
            self.assertEqual(result['complete_diagnostic']['status'], 'CANCELLED')
            self.assertFalse(result['session_valid'])
            self.assertEqual(result['findings'], [])
            event.clear()
            workload.reset_mock()
            benchmark.update(status='SAFETY_STOP', safety_stop='CPU 96 °C')
            benchmark['cpu']['status'] = 'SAFETY_STOP'
            result = engine.run_complete_diagnostic(base, {}, [], cancel_check=event.is_set)
            workload.assert_called_once()
            self.assertTrue(is_finalized_result(result))
            self.assertEqual(result['overall_status'], 'CRITICAL')

    def test_save_rejects_unfinished_and_does_not_overwrite_same_second(self):
        with tempfile.TemporaryDirectory() as tmp:
            for status in ('CANCELLED', 'ERROR', 'RUNNING'):
                result = final_result()
                result['complete_diagnostic'].update(status=status, finalized=False)
                with self.assertRaises(ValueError):
                    engine.save_complete_result(result, tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [])
            a = engine.save_complete_result(final_result(), tmp)
            b = engine.save_complete_result(final_result(), tmp)
            self.assertNotEqual(a, b)


class EvidenceTests(unittest.TestCase):
    def test_empty_windows_is_na_and_has_no_priority(self):
        result = final_result()
        result['complete_diagnostic']['windows'] = {k: {} for k in ('startup', 'services', 'stability', 'drivers')}
        reports = build_component_assessments(result)
        self.assertEqual(next(r for r in reports if r['key'] == 'windows')['status'], 'NO_EVALUABLE')
        self.assertIsNone(select_priority_assessment(reports))

    def test_storage_cache_identity_and_no_healthy_percentage(self):
        t = {'_storage_devices': [{'name': 'Drive A'}], '_storage_health_cache': {0: {'model': 'Drive B', 'health': 100}}}
        self.assertNotIn('health_percent', storage_snapshot(t, [])[0])
        t['_storage_health_cache'][0] = {'model': 'Drive A', 'health': None, 'windows_health_status': 'Healthy'}
        result = final_result()
        result['complete_diagnostic']['hardware']['storage'] = storage_snapshot(t, [])
        report = next(x for x in build_component_assessments(result) if x['key'] == 'storage')
        self.assertEqual(report['facets'][0][1], 'N/A')

    def test_active_gpu_and_renderer_mismatch_do_not_mix_temperatures(self):
        gpus = [{'name': 'Idle', 'usage_percent': 0, 'temperature_c': 30}, {'name': 'Busy', 'usage_percent': 90, 'temperature_c': 70}]
        self.assertEqual(active_gpu(gpus)['name'], 'Busy')
        monitor = engine._StressMonitor(None)
        monitor.rows = [engine._telemetry_row({'_gpus': gpus})]
        item = engine._stress_component({'status': 'OK'}, monitor, renderer='Other')
        self.assertIsNone(item['telemetry']['gpu_temp']['max'])
        item = engine._stress_component({'status': 'OK'}, monitor, renderer='Busy')
        self.assertEqual(item['telemetry']['gpu_temp']['max'], 70)

    def test_ram_capacity_gpu_low_and_storage_source_are_visible(self):
        result = final_result()
        result['complete_diagnostic']['hardware'].update(telemetry_snapshot={'ram_total_gb': 16}, storage=[{'name': 'A', 'health': 94, 'health_source': 'NVMe', 'wear_percent': 6, 'wear_quantitative_reliable': True}])
        result['complete_diagnostic']['benchmark'] = {'gpu': {'status': 'OK', 'frames_per_s': 40, 'fps_1pct_low': 28}}
        self.assertIn('16.00 GB', str(build_component_evidence(result, 'ram')))
        self.assertIn('28.0 FPS', str(build_component_evidence(result, 'gpu')))
        self.assertIn('94%', str(build_component_evidence(result, 'storage')))
        self.assertIn('6%', str(build_component_evidence(result, 'storage')))


class RealWidgetTests(unittest.TestCase):
    def test_cancel_repeat_complete_reuses_real_tk_panel(self):
        import customtkinter as ctk
        from gui.diagnostic_view import DiagnosticExperiencePanel
        import tkinter
        try:
            root = ctk.CTk()
        except tkinter.TclError as exc:
            self.skipTest('Tcl/Tk no disponible en el entorno: ' + str(exc).splitlines()[0])
        root.withdraw()
        root.cancel_diagnostic_session = Mock()
        root.start_diagnostic_session = Mock()
        root._complete_diagnostic_started_at = time.time()
        root.latest_pdf_path = None
        root.diagnostic_session = AdaptiveDiagnosticSession()
        try:
            with patch.object(DiagnosticExperiencePanel, '_load_identity_async'):
                panel = DiagnosticExperiencePanel(root)
            for _ in range(3):
                panel.show_cancelled()
                self.assertEqual(panel.btn_cancel.cget('text'), 'Diagnosticar de nuevo')
                panel.reset_for_run()
                panel.update_progress({'progress': .1})
                self.assertFalse(panel._finished)
                self.assertEqual(panel.btn_cancel.cget('text'), 'Cancelar')
                self.assertEqual(panel.btn_cancel.winfo_manager(), 'grid')
                self.assertEqual(panel.result_actions.winfo_manager(), '')
                panel.update_complete_progress({'progress': .75, 'stage': 'Benchmark'})
                panel.show_complete(final_result())
                self.assertTrue(panel._finished)
                self.assertEqual(panel.component_report.winfo_manager(), 'grid')
                self.assertEqual(panel.btn_pdf.cget('state'), 'normal')
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
