from pathlib import Path
from unittest.mock import patch

from core.version import VERSION, STAGE
from core import complete_diagnostic as diag


def _base():
    return {
        'session_valid': True,
        'duration_seconds': 180.0,
        'overall_status': 'NORMAL',
        'completion_status': 'COMPLETED',
        'findings': [],
        'statistics': {},
        'adaptive_diagnostic': {'finish_reason': 'Tiempo objetivo completado'},
    }


def _snapshot():
    return {
        'cpu_usage': 18.0,
        'cpu_temp': 61.0,
        'cpu_ghz': 4.0,
        'ram_usage': 42.0,
        '_gpus': [{
            'name': 'NVIDIA Test GPU',
            'usage_percent': 22.0,
            'temperature_c': 60.0,
            'core_clock_mhz': 1750.0,
            'fan_rpm': 1800.0,
        }],
        '_storage_devices': [{'name': 'Test SSD', 'temperature_c': 39.0}],
    }


def _benchmark():
    def component(name):
        metric = {'cpu': 'cpu_temp', 'gpu': 'gpu_temp', 'ram': 'ram_usage', 'ssd': 'storage_temperature'}[name]
        return {
            'status': 'OK',
            'value': 100.0,
            'unit': 'test-unit',
            'telemetry': {
                'during_sample_count': 3,
                metric: {'samples': 3, 'min': 1.0, 'max': 2.0, 'avg': 1.5},
            },
        }
    return {
        'status': 'OK',
        'cpu': component('cpu'),
        'gpu': component('gpu'),
        'ram': component('ram'),
        'ssd': component('ssd'),
        'safety_stop': None,
    }


def _stress():
    return {
        'status': 'OK',
        'components': {
            'cpu': {'status': 'OK', 'duration_s': 8.0, 'telemetry': {}},
            'ram': {'status': 'OK', 'duration_s': 8.0, 'telemetry': {}},
            'gpu': {'status': 'OK', 'duration_s': 8.0, 'telemetry': {}},
        },
        'safety_stop': None,
    }


def test_version_and_stage():
    assert VERSION == '164'
    assert STAGE == 'DIAGNOSTICO_TOTAL_6_0_AI_CLEANUP_PDF'


def test_full_11_phase_flow_finishes_and_freezes_ai():
    windows_ok = {'items': [], 'count': 0, 'severity': 'NORMAL', 'device_problems': 0}
    ai = {
        'status': 'OK',
        'year': 2026,
        'current_year': 2026,
        'executive_summary': 'Equipo evaluado con evidencia real.',
        'hardware_relevance': [
            {'component_id': 'CPU', 'detected_hardware': 'CPU Test', 'classification': 'ESTANDAR'}
        ],
        'limitations': [],
    }
    cleanup = {
        'status': 'OK', 'mutating': True, 'deleted_files': 4, 'deleted_bytes': 1024,
        'summary': '4 archivos temporales eliminados', 'policy': 'ALLOWLIST_RECREATABLE_ONLY_REAL_OR_NA',
    }
    audio = {
        'status': 'PRUEBA TÉCNICA COMPLETADA', 'technical_playback_executed': True,
        'acoustic_confirmation': None, 'result': {},
    }
    fans = {'status': 'MEASURED', 'interpretation': 'RPM observadas durante carga'}
    integrity = {'overall_state': 'OK', 'steps': []}
    filesystem = {'status': 'OK', 'drive': 'C:'}

    progress_rows = []
    with patch.object(diag, 'collect_battery_health', return_value={'present': True, 'health_percent': 90}), \
         patch.object(diag, 'storage_snapshot', return_value=[]), \
         patch.object(diag, 'analyze_startup', return_value=windows_ok), \
         patch.object(diag, 'analyze_services', return_value=windows_ok), \
         patch.object(diag, 'analyze_crashes', return_value=windows_ok), \
         patch.object(diag, 'analyze_drivers', return_value=windows_ok), \
         patch.object(diag, 'run_integrity_diagnostic', return_value=integrity), \
         patch.object(diag, '_filesystem_integrity_scan', return_value=filesystem), \
         patch.object(diag, 'run_benchmark_suite', return_value=_benchmark()), \
         patch.object(diag, 'run_stress_suite', return_value=_stress()), \
         patch.object(diag, '_fan_observation', return_value=fans), \
         patch.object(diag, '_audio_observation', return_value=audio), \
         patch.object(diag, '_safe_cleanup_phase', return_value=cleanup), \
         patch.object(diag, 'analyze_report_with_ai', return_value=ai):
        result = diag.run_complete_diagnostic(
            _base(), _snapshot(), [], telemetry_sampler=_snapshot,
            progress_callback=lambda fraction, stage, detail='': progress_rows.append(float(fraction)),
        )

    block = result['complete_diagnostic']
    assert block['version'] == '6.0-v164'
    assert block['finalized'] is True
    assert block['pdf_optional'] is True
    assert block['status'] == 'COMPLETE'
    assert block['phase_coverage'] == {'completed': 11, 'total': 11, 'partial': False}
    assert block['phase_order'] == [
        'desktop', 'hardware', 'windows', 'integrity', 'benchmark', 'stress',
        'fans', 'audio', 'cleanup', 'correlation', 'ai',
    ]
    assert block['ai_analysis'] == ai
    assert result['_ai_analysis'] == ai
    assert block['cleanup']['deleted_files'] == 4
    assert block['repair_actions_executed'] is False
    assert block['cleanup_actions_executed'] is True
    assert block['policy']['real_or_na'] is True
    assert block['policy']['benchmark_and_stress_are_distinct'] is True
    assert block['policy']['automatic_stress'] is True
    assert block['policy']['stress_publishes_performance_score'] is False
    assert block['policy']['automatic_windows_repairs'] is False
    assert block['policy']['automatic_safe_cleanup'] is True
    assert block['policy']['audio_requires_human_confirmation'] is True
    assert block['policy']['ai_interprets_real_evidence_only'] is True
    assert block['policy']['hardware_relevance_uses_runtime_year'] is True
    assert progress_rows == sorted(progress_rows)
    assert progress_rows[-1] == 1.0


def test_ui_and_pdf_contract_are_present():
    ui = Path('gui/diagnostic_view.py').read_text(encoding='utf-8')
    main = Path('main.py').read_text(encoding='utf-8')
    report_generator = Path('core/report_generator.py').read_text(encoding='utf-8')
    report_builder = Path('core/report_builder.py').read_text(encoding='utf-8')

    assert "text='Generar PDF'" in ui
    assert "complete.get('ai_analysis')" in ui
    assert 'Vigencia' in ui
    assert 'Limpieza segura:' in ui
    assert 'start_diagnostic_session(force_new=True)' in main
    assert "complete.get('ai_analysis')" in report_generator
    assert 'CorePulseIcon.png' in report_builder
    assert 'Diagnóstico Total 6.0' in report_builder


def test_no_external_ranking_or_automatic_windows_repairs_in_contract():
    source = Path('core/complete_diagnostic.py').read_text(encoding='utf-8')
    run_block = source[source.index('def run_complete_diagnostic('):]
    assert "'benchmark_has_external_ranking': False" in run_block
    assert "'automatic_windows_repairs': False" in run_block
    assert "'real_or_na': True" in run_block
    assert "'automatic_safe_cleanup': True" in run_block
    assert "'audio_requires_human_confirmation': True" in run_block
