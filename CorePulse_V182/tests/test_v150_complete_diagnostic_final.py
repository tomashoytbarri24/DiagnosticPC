from pathlib import Path
import threading

ROOT = Path(__file__).resolve().parents[1]


def test_v150_version_stage():
    ns = {}
    exec((ROOT / 'core' / 'version.py').read_text(encoding='utf-8'), ns)
    assert str(ns["VERSION"]).isdigit()
    assert bool(ns["STAGE"])


def test_diagnostic_session_can_cancel_without_final_result():
    from core.diagnostic_session import DiagnosticSession
    session = DiagnosticSession(duration_seconds=30)
    session.start()
    assert session.active
    session.cancel()
    assert not session.active
    assert not session.completed
    assert session.result is None


def test_complete_diagnostic_declares_final_policy_and_phase_coverage():
    src = (ROOT / 'core' / 'complete_diagnostic.py').read_text(encoding='utf-8')
    assert "'version': '3.0-v150'" in src
    assert "'phase_coverage'" in src
    assert "'user_cancellable': True" in src
    assert "'history_is_informational_only': True" in src
    assert "'automatic_repairs': False" in src
    assert "result['diagnostic_mode'] = 'COMPLETE_3_0'" in src


def test_benchmark_suite_supports_cooperative_cancel():
    src = (ROOT / 'core' / 'benchmark_engine.py').read_text(encoding='utf-8')
    assert 'cancel_check: Optional[Callable[[], bool]] = None' in src
    assert "'status': 'CANCELLED' if cancelled()" in src


def _sample(status='WARNING'):
    return {
        'overall_status': status,
        'statistics': {'cpu': {}, 'ram': {}, 'gpus': {}, 'storage': {}},
        'findings': [],
        'complete_diagnostic': {
            'status': 'COMPLETE',
            'hardware': {'storage': [], 'battery': {'present': False}},
            'windows': {'startup': {}, 'services': {}, 'stability': {}, 'drivers': {}},
            'stress_test': {'status': 'OK', 'components': {
                'cpu': {'status': 'OK'}, 'gpu': {'status': 'OK'}, 'ram': {'status': 'OK'}
            }},
            'benchmark': {
                'cpu': {'status': 'OK'}, 'gpu': {'status': 'OK'},
                'ram': {'status': 'OK'}, 'ssd': {'status': 'OK'},
            },
        },
    }


def test_previous_comparison_is_informational_only():
    from core.diagnostic_history import build_diagnostic_comparison
    previous = _sample('NORMAL')
    current = _sample('WARNING')
    current['findings'] = [{
        'component': 'DRIVERS', 'status': 'WARNING', 'title': 'Drivers',
        'explanation': 'Problema real', 'evidence': ['1 problema']
    }]
    comparison = build_diagnostic_comparison(current, previous)
    assert comparison['available'] is True
    assert comparison['history_used_as_current_fault_source'] is False
    assert comparison['policy'] == 'INFORMATIONAL_ONLY_NOT_CURRENT_FAULT_SOURCE'
    assert any(x['key'] == 'windows' for x in comparison['component_changes'])


def test_ui_exposes_cancel_coverage_comparison_and_evidence():
    src = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert "text='Cancelar'" in src
    assert 'cancel_diagnostic_session' in src
    assert 'def show_cancelled' in src
    assert "text='COBERTURA'" in src
    assert 'Comparación anterior:' in src
    assert "text='Ver evidencia'" in src


def test_pdf_includes_final_coverage_and_comparison():
    src = (ROOT / 'core' / 'report_builder.py').read_text(encoding='utf-8')
    assert 'Diagnóstico Completo 3.0' in src
    assert 'Cobertura del diagnóstico' in src
    assert 'Comparación con diagnóstico anterior' in src


def test_main_invalidates_cancelled_worker_callbacks():
    src = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert '_diagnostic_run_token' in src
    assert '_diagnostic_cancel_event' in src
    assert 'def cancel_diagnostic_session' in src
    assert 'run_token != self._diagnostic_run_token' in src
