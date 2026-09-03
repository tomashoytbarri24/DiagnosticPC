"""Regresión de diagnóstico determinístico y tutoriales verificables sin hardware hardcodeado."""
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.ai_evidence_research import _verify_tutorial
from core.diagnostic_pipeline import integrate_current_diagnostic_pipeline
from core.diagnostic_session import DiagnosticSession
from core.env_config import ai_runtime_status
from core.ai_report_engine import _sanitize_plan_actions


def stat(samples, avg, maxv, minv=None):
    return {'samples': samples, 'min': avg if minv is None else minv, 'max': maxv, 'avg': avg, 'median': avg}


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok

session = DiagnosticSession(duration_seconds=30)
stats = {
    'cpu': {
        'usage_percent': stat(30, 40.0, 80.0), 'package_temp_c': stat(30, 70.0, 85.0),
        'core_max_temp_c': stat(30, 72.0, 87.0), 'core_average_temp_c': stat(30, 68.0, 82.0),
        'distance_to_tjmax_min_c': stat(30, 25.0, 30.0, 15.0), 'clock_avg_ghz': stat(30, 3.5, 4.2),
        'package_power_w': stat(30, 35.0, 65.0), 'seconds_within_5c_tjmax': 0, 'seconds_within_10c_tjmax': 0,
    },
    'ram': {'usage_percent': stat(30, 92.5, 96.0, 89.0), 'seconds_over_85_percent': 30, 'seconds_over_90_percent': 24, 'seconds_over_95_percent': 4},
    'gpus': {},
    'storage': {
        'ExampleDrive Q700': {
            'temperature_c': stat(30, 45.0, 49.0), 'warning_temperature_c': 80.0, 'critical_temperature_c': 90.0,
            'seconds_at_or_above_warning': 0, 'seconds_at_or_above_critical': 0, 'life_percent': 93.0,
            'used_space_percent': 93.0, 'power_on_hours': 1000.0,
        }
    },
    'battery': None,
}
findings = session._build_findings(stats)
ram_warning = [f for f in findings if f.component == 'RAM' and f.status == 'WARNING']
storage_warning = [f for f in findings if f.component.startswith('STORAGE:') and f.status == 'WARNING' and 'espacio' in f.title.lower()]

diag = {'overall_status': 'WARNING', 'sample_count': 30, 'duration_seconds': 30, 'findings': [f.__dict__ for f in findings], 'statistics': stats}
pipeline = integrate_current_diagnostic_pipeline(
    diag,
    {'ram_usage': 92.5, '_metrics': {'ram_usage': {'value': 92.5, 'unit': '%', 'source': 'test', 'quality': 'VALID'}}},
    [],
    device_identity={'form_factor': 'LAPTOP', 'manufacturer': 'Example Systems', 'model': 'Notebook Z14'},
)
rec_text = ' '.join(' '.join(r.get('steps') or []) for r in pipeline.get('recommendations') or []).lower()
queries = ' '.join(str(r.get('tutorial_query') or '') for r in pipeline.get('recommendations') or []).lower()

url = 'https://www.youtube.com/watch?v=corepulse-test'
evidence = f'web_search result: {url}'
verified = _verify_tutorial(
    {'url': url}, evidence, 'Notebook Z14', component_type='CPU',
    problem_title='CPU sostenidamente muy cerca de TjMax',
    tutorial_action='cooling fan cleaning heatsink thermal paste disassembly',
    oembed_func=lambda _: {'title': 'Example Systems Notebook Z14 Cooling Fan Cleaning Thermal Paste', 'channel': 'Test'},
)
wrong_action = _verify_tutorial(
    {'url': url}, evidence, 'Notebook Z14', component_type='RAM',
    problem_title='Uso alto sostenido de memoria', tutorial_action='RAM upgrade memory slot disassembly',
    oembed_func=lambda _: {'title': 'Example Systems Notebook Z14 Performance Review', 'channel': 'Test'},
)
runtime = ai_runtime_status()
unverified_gpu_laptop = _sanitize_plan_actions(
    ['Reemplazar la GPU por una más nueva.'], form='LAPTOP', ctype='GPU', upgrade_status='UNVERIFIED'
)
unverified_gpu_desktop = _sanitize_plan_actions(
    ['Reemplazar la GPU por una más nueva.'], form='DESKTOP', ctype='GPU', upgrade_status='UNVERIFIED'
)
verified_gpu_desktop = _sanitize_plan_actions(
    ['Reemplazar la GPU por una más nueva.'], form='DESKTOP', ctype='GPU', upgrade_status='VERIFIED_UPGRADEABLE'
)
results = [
    check('ram_pressure_is_deterministic_warning', bool(ram_warning)),
    check('storage_pressure_is_deterministic_warning', bool(storage_warning)),
    check('deterministic_pipeline_has_actions', pipeline.get('recommendation_count', 0) >= 2),
    check('ram_actions_are_actionable', 'procesos' in rec_text or 'administrador de tareas' in rec_text),
    check('storage_actions_are_capacity_specific', 'archivos' in rec_text and ('margen' in rec_text or 'espacio' in rec_text)),
    check('tutorial_query_uses_runtime_exact_model', 'notebook z14' in queries),
    check('exact_model_and_action_video_verified', verified.get('status') == 'VERIFIED_EXACT'),
    check('wrong_action_video_rejected', wrong_action.get('status') == 'NOT_FOUND'),
    check('runtime_status_does_not_expose_secret', runtime.get('secret_exposed') is False),
    check('unverified_replacement_blocked_on_laptop_without_assumption', 'verificar primero' in unverified_gpu_laptop[0].lower()),
    check('unverified_replacement_blocked_on_desktop_too', 'verificar primero' in unverified_gpu_desktop[0].lower()),
    check('verified_replacement_not_blocked_by_form_factor', verified_gpu_desktop[0].startswith('Reemplazar')),
]
print('\nRESULTADO:', 'PASS' if all(results) else 'FAIL')
raise SystemExit(0 if all(results) else 1)
