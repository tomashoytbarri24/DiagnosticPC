"""Prueba de humo del constructor PDF vigente sin invocar servicios externos."""
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.report_builder import _machine_display_label, build_pdf_report
from core.version import VERSION, VERSION_LABEL


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok

identity = {
    'manufacturer': 'Example Systems', 'model': 'Notebook Z14', 'display_model': 'Example Systems Notebook Z14',
    'form_factor': 'LAPTOP',
    'motherboard': {'manufacturer': 'BoardWorks', 'model': 'BW-Z14'},
    'bios': {'manufacturer': 'Firmware Labs', 'version': '1.2.3'},
}
inventory = {
    'identity': identity,
    'cpu': {'name': 'Example CPU X600', 'wmi': {'manufacturer': 'Nova Silicon', 'cores': 8, 'threads': 16, 'max_clock_ghz': 4.5}, 'current_ghz': 3.2},
    'ram': {'total_gb': 24.0, 'module_count': 2, 'modules': []},
    'gpus': [{'name': 'Nebula Accelerator X900', 'vendor': 'Nova Silicon', 'temperature_c': 62.0, 'usage_percent': 40.0}],
    'storage': [{'name': 'ExampleDrive Q700', 'model': 'ExampleDrive Q700', 'total_space_gb': 1024.0, 'temperature_c': 44.0, 'life_percent': 98.0, 'used_space_percent': 55.0}],
    'battery': {'charge_percent': 80.0},
}
telemetry = {
    'cpu_name': 'Example CPU X600', 'cpu_usage': 32.0, 'cpu_temp': 68.0, 'cpu_ghz': 3.2,
    'ram_total_gb': 24.0, 'ram_usage': 52.0, 'gpu_name': 'Nebula Accelerator X900', 'gpu_usage': 40.0, 'gpu_temp': 62.0,
    '_hardware_inventory': inventory,
    '_metrics': {
        'cpu_usage': {'value': 32.0, 'unit': '%', 'source': 'test', 'quality': 'VALID'},
        'cpu_temp': {'value': 68.0, 'unit': '°C', 'source': 'test', 'quality': 'VALID'},
        'ram_usage': {'value': 52.0, 'unit': '%', 'source': 'test', 'quality': 'VALID'},
    },
}
disks = [{'name': 'ExampleDrive Q700', 'model': 'ExampleDrive Q700', 'total_space_gb': 1024.0, 'used_space_percent': 55.0, 'temperature_c': 44.0, 'life_percent': 98.0}]
diag = {
    'overall_status': 'NORMAL', 'session_valid': True, 'duration_seconds': 120, 'sample_count': 120,
    'findings': [{'component': 'CPU', 'status': 'INFO', 'title': 'Lecturas dentro de la evidencia disponible', 'explanation': 'Sin condición correctiva sostenida.', 'evidence': ['CPU 68 °C'], 'rule_source': 'test'}],
    'statistics': {'cpu': {}, 'ram': {}, 'gpus': {}, 'storage': {}, 'battery': None},
}
diag['_intelligent_recommendations'] = {
    'diagnostic_status': 'NORMAL',
    'scope': 'CURRENT_DIAGNOSTIC_ONLY',
    'recommendations': [],
    'recommendation_count': 0,
    'informational_findings': [],
    'informational_count': 0,
    'runtime_integration': {
        'diagnostic_status_original': 'NORMAL',
        'scope': 'CURRENT_DIAGNOSTIC_ONLY',
        'history_used_as_current_fault_source': False,
        'external_ai_used': False,
    },
}
ai = {
    'status': 'OK', 'provider': 'GROQ', 'model': 'openai/gpt-oss-120b', 'current_year': 2026,
    'executive_summary': 'La sesión de prueba se mantuvo estable.',
    'hardware_relevance': [
        {'component_id': 'CPU', 'component_type': 'CPU', 'detected_hardware': 'Example CPU X600', 'classification': 'ESTANDAR', 'confidence': 'MEDIA', 'reason': 'Evidencia comparativa suficiente.'},
        {'component_id': 'RAM', 'component_type': 'RAM', 'detected_hardware': '24 GB RAM', 'classification': 'ESTANDAR', 'confidence': 'ALTA', 'reason': 'Capacidad vigente con evidencia consistente.'},
        {'component_id': 'GPU:0', 'component_type': 'GPU', 'detected_hardware': 'Nebula Accelerator X900', 'classification': 'ESTANDAR', 'confidence': 'MEDIA', 'reason': 'Posición mainstream verificada.'},
        {'component_id': 'STORAGE:0', 'component_type': 'STORAGE', 'detected_hardware': 'ExampleDrive Q700', 'classification': 'JUSTO', 'confidence': 'MEDIA', 'reason': 'Vigencia comparativa suficiente.'},
    ],
    'problem_recommendations': [], 'recommendations': [], 'limitations': [],
    'research': {'status': 'OK', 'source_count': 8, 'sources': [], 'search_executed': True, 'reason': 'Investigación sintética de prueba.'},
}

out = ROOT / 'data' / '_smoke_pdf.pdf'
out.parent.mkdir(parents=True, exist_ok=True)
path = build_pdf_report(telemetry, disks, 92, out, diagnostic_result=diag, ai=ai)
content = out.read_bytes() if out.exists() else b''
results = [
    check('version_authority_available', VERSION_LABEL == f'V{VERSION}'),
    check('notebook_header_does_not_duplicate_manufacturer', _machine_display_label(identity) == 'Example Systems Notebook Z14'),
    check('desktop_header_prefers_platform_label', _machine_display_label({
        'manufacturer': 'Example Systems',
        'display_model': 'PC de escritorio · BoardWorks BW-X1',
        'form_factor': 'DESKTOP',
    }) == 'PC de escritorio · BoardWorks BW-X1'),
    check('raw_model_still_keeps_manufacturer', _machine_display_label({
        'manufacturer': 'Example Systems',
        'model': 'Notebook Z14',
        'form_factor': 'LAPTOP',
    }) == 'Example Systems Notebook Z14'),
    check('pdf_generated', Path(path).exists() and len(content) > 1500 and content.startswith(b'%PDF-')),
    check('pdf_has_multiple_pages', content.count(b'/Type /Page') >= 2),
]
try:
    out.unlink(missing_ok=True)
except Exception:
    pass
print('\nRESULTADO:', 'PASS' if all(results) else 'FAIL')
raise SystemExit(0 if all(results) else 1)
