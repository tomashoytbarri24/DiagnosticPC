from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sample_result():
    return {
        'overall_status': 'WARNING',
        'sample_count': 35,
        'statistics': {
            'cpu': {
                'usage_percent': {'avg': 19, 'max': 66},
                'package_temp_c': {'avg': 49, 'max': 70},
                'clock_avg_ghz': {'avg': 3.2, 'min': 1.8, 'max': 4.3},
            },
            'ram': {'usage_percent': {'avg': 44, 'max': 63}},
            'gpus': {
                'RTX Test': {
                    'usage_percent': {'avg': 7, 'max': 31},
                    'temperature_c': {'avg': 47, 'max': 57},
                    'core_clock_mhz': {'avg': 812, 'max': 1785},
                }
            },
            'storage': {},
        },
        'findings': [{
            'component': 'DRIVERS', 'status': 'WARNING',
            'title': 'Windows reporta dispositivos con problema',
            'explanation': 'Existe evidencia PnP actual.',
            'evidence': ['1 dispositivo con problema'],
        }],
        'complete_diagnostic': {
            'finalized': True,
            'status': 'COMPLETE',
            'phase_coverage': {'completed': 7, 'total': 7, 'partial': False},
            'hardware': {
                'storage': [{
                    'name': 'NVMe Test', 'life_percent': 93, 'temperature_c': 48,
                    'health_source': 'Windows Storage Reliability', 'used_percent': 61,
                }],
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
                    'cpu': {'status': 'OK', 'duration_s': 10, 'telemetry': {'cpu_usage': {'max': 100}, 'cpu_temp': {'max': 79}}},
                    'gpu': {'status': 'OK', 'duration_s': 9, 'renderer': 'RTX Test', 'telemetry': {'gpu_usage': {'max': 99}, 'gpu_temp': {'max': 68}}},
                    'ram': {'status': 'OK', 'duration_s': 7, 'working_set_mb': 192},
                },
            },
            'benchmark': {
                'cpu': {'status': 'OK', 'value': 5200, 'unit': 'MB/s'},
                'gpu': {'status': 'OK', 'value': 11.5, 'unit': 'Mtri/s'},
                'ram': {'status': 'OK', 'value': 7168, 'unit': 'MB/s'},
                'ssd': {'status': 'OK', 'read_mbps': 1200, 'write_mbps': 850, 'path_root': 'C:\\'},
            },
        },
    }


def test_v160_version_stage():
    ns = {}
    exec((ROOT / 'core' / 'version.py').read_text(encoding='utf-8'), ns)
    assert str(ns["VERSION"]).isdigit()
    assert bool(ns["STAGE"])


def test_cpu_gpu_ram_cards_make_desktop_stress_benchmark_explicit():
    from core.diagnostic_summary import build_component_assessments
    reports = {x['key']: x for x in build_component_assessments(sample_result())}
    for key in ('cpu', 'gpu', 'ram'):
        labels = [row[0] for row in reports[key]['facets']]
        assert labels == ['Escritorio', 'Estrés', 'Benchmark']
        assert reports[key]['facets'][0][1] == 'MEDIDO'


def test_cards_expose_desktop_evidence_without_claiming_health():
    from core.diagnostic_summary import build_component_assessments
    reports = {x['key']: x for x in build_component_assessments(sample_result())}
    assert any(text.startswith('Escritorio:') for text in reports['cpu']['evidence'])
    assert any(text.startswith('Escritorio:') for text in reports['gpu']['evidence'])
    assert any(text.startswith('Escritorio:') for text in reports['ram']['evidence'])


def test_storage_separates_health_space_and_benchmark():
    from core.diagnostic_summary import build_component_assessments
    storage = next(x for x in build_component_assessments(sample_result()) if x['key'] == 'storage')
    assert [row[0] for row in storage['facets']] == ['Salud', 'Espacio', 'Benchmark']
    assert storage['facets'][0][1] == '93%'
    assert storage['facets'][1][1] == '61%'


def test_integrated_overview_counts_real_component_states_and_phases():
    from core.diagnostic_summary import build_diagnostic_overview
    overview = build_diagnostic_overview(sample_result())
    assert overview['total_areas'] == 6
    assert overview['warning_count'] >= 1
    assert overview['completed_phases'] == 7
    assert overview['total_phases'] == 7
    assert '7/7 fases' in overview['headline']
    assert overview['policy'] == 'COUNTS_ONLY_FROM_REAL_COMPONENT_ASSESSMENTS'


def test_ui_and_pdf_share_integrated_overview():
    ui = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    pdf = (ROOT / 'core' / 'report_builder.py').read_text(encoding='utf-8')
    assert 'build_diagnostic_overview' in ui
    assert 'Resumen integral:' in ui
    assert 'ESTADO EN ESCRITORIO + ESTRÉS + BENCHMARK + WINDOWS' in ui
    assert 'build_diagnostic_overview' in pdf
    assert "'Resumen integral'" in pdf


def test_complete_diagnostic_contract_is_v160_and_safe():
    src = (ROOT / 'core' / 'complete_diagnostic.py').read_text(encoding='utf-8')
    assert "'version': '3.1-v160'" in src
    assert "result['diagnostic_mode'] = 'COMPLETE_3_1'" in src
    assert "'stress_and_benchmark_are_distinct': True" in src
    assert "'automatic_repairs': False" in src
    assert "'real_or_na': True" in src
