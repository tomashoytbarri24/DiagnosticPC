from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sample_result():
    return {
        'overall_status': 'WARNING',
        'sample_count': 30,
        'statistics': {
            'cpu': {
                'usage_percent': {'avg': 21, 'max': 67},
                'package_temp_c': {'avg': 52, 'max': 71},
                'clock_avg_ghz': {'avg': 3.1, 'min': 1.7, 'max': 4.2},
                'distance_to_tjmax_min_c': {'min': 29},
            },
            'ram': {
                'usage_percent': {'avg': 42, 'max': 61},
                'seconds_over_85_percent': 0,
                'seconds_over_95_percent': 0,
            },
            'gpus': {
                'RTX Test': {
                    'usage_percent': {'avg': 8, 'max': 35},
                    'temperature_c': {'avg': 48, 'max': 58},
                }
            },
            'storage': {},
        },
        'findings': [{
            'component': 'DRIVERS', 'status': 'WARNING',
            'title': 'Windows reporta dispositivos con problema',
            'explanation': 'Win32_PnPEntity expone un problema actual.',
            'evidence': ['1 dispositivo con problema'],
        }],
        'complete_diagnostic': {
            'hardware': {
                'storage': [{'name': 'NVMe Test', 'life_percent': None, 'temperature_c': 48, 'health_source': 'Windows Storage'}],
                'battery': {'present': True, 'health_percent': 88, 'degradation_percent': 12, 'cycle_count': 210},
            },
            'windows': {
                'startup': {'count': 8, 'items': []},
                'services': {'count': 120},
                'stability': {'severity': 'NORMAL'},
                'drivers': {'count': 84, 'device_problems': 1},
            },
            'stress_test': {
                'status': 'OK',
                'components': {
                    'cpu': {'status': 'OK', 'duration_s': 10, 'provider': 'CorePulse', 'telemetry': {'cpu_usage': {'max': 100}, 'cpu_temp': {'max': 79}, 'cpu_ghz': {'min': 2.7}, 'throttling': {'cpu': {'state': 'N/A'}}}},
                    'gpu': {'status': 'OK', 'duration_s': 9, 'renderer': 'RTX Test', 'telemetry': {'gpu_usage': {'max': 99}, 'gpu_temp': {'max': 68}, 'throttling': {'gpu': {'state': 'N/A'}}}},
                    'ram': {'status': 'OK', 'duration_s': 7, 'working_set_mb': 192, 'provider': 'CorePulse'},
                },
            },
            'benchmark': {
                'cpu': {'status': 'OK', 'value': 5200, 'unit': 'MB/s', 'duration_s': 12, 'provider': 'CorePulse SHA-256'},
                'gpu': {'status': 'OK', 'value': 11.5, 'unit': 'Mtri/s', 'frames_per_s': 44, 'renderer': 'RTX Test', 'duration_s': 12},
                'ram': {'status': 'OK', 'value': 7168, 'unit': 'MB/s', 'duration_s': 8, 'provider': 'CorePulse RAM'},
                'ssd': {'status': 'OK', 'read_mbps': 1200, 'write_mbps': 850, 'size_mb': 1024, 'path_root': 'C:\\', 'duration_s': 10},
            },
        },
    }


def test_v149_version_stage():
    ns = {}
    exec((ROOT / 'core' / 'version.py').read_text(encoding='utf-8'), ns)
    assert ns['VERSION'] == '149'
    assert ns['STAGE'] == 'COMPLETE_DIAGNOSTIC_TRACEABLE_EVIDENCE'


def test_cpu_evidence_separates_desktop_stress_benchmark():
    from core.diagnostic_summary import build_component_evidence
    detail = build_component_evidence(sample_result(), 'cpu')
    assert [x['title'] for x in detail['sections'][:3]] == ['Escritorio', 'Estrés', 'Benchmark']
    assert any(r['label'] == 'Temperatura máxima' and '79' in r['value'] for r in detail['sections'][1]['rows'])
    assert any(r['label'] == 'Resultado' and '5200' in r['value'] for r in detail['sections'][2]['rows'])


def test_storage_evidence_keeps_health_na_but_benchmark_real():
    from core.diagnostic_summary import build_component_evidence
    detail = build_component_evidence(sample_result(), 'storage')
    health = detail['sections'][0]
    bench = detail['sections'][1]
    assert 'N/A' in health['rows'][0]['value']
    assert any(r['label'] == 'Lectura secuencial' and '1200' in r['value'] for r in bench['rows'])
    assert any(r['label'] == 'Volumen probado' and 'C:' in r['value'] for r in bench['rows'])


def test_windows_evidence_exposes_driver_problem_without_repair():
    from core.diagnostic_summary import build_component_evidence
    detail = build_component_evidence(sample_result(), 'windows')
    drivers = next(x for x in detail['sections'] if x['title'] == 'Controladores')
    assert any(r['label'] == 'Dispositivos con problema' and r['value'] == '1' for r in drivers['rows'])
    assert 'no instala' in drivers['note'].lower()


def test_ui_has_distinct_evidence_and_module_actions():
    src = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert "text='Ver evidencia'" in src
    assert 'def _show_component_evidence' in src
    assert 'build_component_evidence' in src
    assert "'evidence_action': evidence_action" in src
    assert "'action': action" in src


def test_evidence_panel_is_inline_not_a_new_toplevel():
    src = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    region = src[src.index('    def _show_component_evidence'):src.index('    def _component_action')]
    assert 'CTkToplevel' not in region
    assert 'self.evidence_card.grid(' in region


def test_pdf_reuses_traceable_evidence_builder():
    src = (ROOT / 'core' / 'report_builder.py').read_text(encoding='utf-8')
    assert 'build_component_evidence(diag' in src
    assert 'Evidencia detallada por componente' in src


def test_complete_diagnostic_policy_stays_safe():
    src = (ROOT / 'core' / 'complete_diagnostic.py').read_text(encoding='utf-8')
    assert "'version': '2.2-v149'" in src
    assert "'real_or_na': True" in src
    assert "'stress_and_benchmark_are_distinct': True" in src
    assert "'automatic_repairs': False" in src
