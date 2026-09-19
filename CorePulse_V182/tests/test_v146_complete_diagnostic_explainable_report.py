from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sample_result():
    return {
        'overall_status': 'WARNING',
        'findings': [
            {
                'component': 'DRIVERS', 'status': 'WARNING',
                'title': 'Windows reporta dispositivos con problema',
                'explanation': 'Win32_PnPEntity expone dispositivos con un código de problema actual.',
                'evidence': ['2 dispositivo(s) con problema'],
            }
        ],
        'complete_diagnostic': {
            'hardware': {
                'storage': [{'name': 'NVMe', 'life_percent': None, 'temperature_c': 51}],
                'battery': {'present': True, 'health_percent': 88, 'degradation_percent': 12, 'cycle_count': 240},
            },
            'windows': {
                'drivers': {'device_problems': 2},
                'startup': {'count': 8, 'items': []},
                'stability': {'severity': 'NORMAL'},
            },
            'stress_test': {
                'status': 'OK',
                'components': {
                    'cpu': {'status': 'OK', 'telemetry': {'cpu_temp': {'max': 78}, 'cpu_usage': {'max': 100}}},
                    'gpu': {'status': 'OK', 'telemetry': {'gpu_temp': {'max': 69}, 'gpu_usage': {'max': 99}}},
                    'ram': {'status': 'OK', 'working_set_mb': 192},
                },
            },
            'benchmark': {
                'cpu': {'status': 'OK', 'value': 5200, 'unit': 'MB/s'},
                'gpu': {'status': 'OK', 'value': 11.5, 'unit': 'Mtri/s'},
                'ram': {'status': 'OK', 'value': 7168, 'unit': 'MB/s'},
                'ssd': {'status': 'OK', 'read_mbps': 1200, 'write_mbps': 850},
            },
        },
    }


def test_v146_version_stage():
    ns = {}
    exec((ROOT / 'core' / 'version.py').read_text(encoding='utf-8'), ns)
    assert str(ns["VERSION"]).isdigit()
    assert bool(ns["STAGE"])


def test_component_assessments_separate_stress_and_performance():
    from core.diagnostic_summary import build_component_assessments
    reports = {x['key']: x for x in build_component_assessments(_sample_result())}
    assert [x[0] for x in reports['cpu']['facets']] == ['Estado', 'Estrés', 'Rendimiento']
    assert reports['cpu']['facets'][1][1] == 'OK'
    assert reports['cpu']['facets'][2][1] == 'MEDIDO'
    assert reports['gpu']['facets'][2][1] == 'MEDIDO'
    assert reports['ram']['facets'][2][1] == 'MEDIDO'


def test_storage_detection_does_not_fake_physical_health():
    from core.diagnostic_summary import build_component_assessments
    reports = {x['key']: x for x in build_component_assessments(_sample_result())}
    assert reports['storage']['status'] == 'NO_EVALUABLE'
    assert reports['storage']['facets'][0][0] == 'Salud'
    assert reports['storage']['facets'][0][1] == 'N/A'
    assert reports['storage']['facets'][2][1] == 'MEDIDO'


def test_priority_points_to_real_warning():
    from core.diagnostic_summary import build_component_assessments, select_priority_assessment
    priority = select_priority_assessment(build_component_assessments(_sample_result()))
    assert priority is not None
    assert priority['key'] == 'windows'
    assert priority['status'] == 'WARNING'
    assert 'dispositivos' in priority['summary'].lower()


def test_ui_has_priority_and_three_facets_without_auto_repair():
    src = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert "text='PRIORIDAD'" in src
    assert "'facets': facet_refs" in src
    assert "select_priority_assessment(reports)" in src
    assert 'repair_windows' not in src


def test_pdf_reuses_same_interpretation():
    src = (ROOT / 'core' / 'report_builder.py').read_text(encoding='utf-8')
    assert 'build_component_assessments(diag)' in src
    assert 'select_priority_assessment(assessments)' in src
    assert "Diagnóstico Completo 2.1" in src


def test_complete_policy_stays_real_or_na_no_rank_no_auto_repair():
    src = (ROOT / 'core' / 'complete_diagnostic.py').read_text(encoding='utf-8')
    assert "'version': '2.1-v146'" in src
    assert "'real_or_na': True" in src
    assert "'stress_and_benchmark_are_distinct': True" in src
    assert "'benchmark_has_external_ranking': False" in src
    assert "'automatic_repairs': False" in src

def test_prefixed_component_findings_are_not_lost():
    from core.diagnostic_summary import build_component_assessments
    result = _sample_result()
    result['findings'].extend([
        {
            'component': 'STORAGE:NVMe MSI', 'status': 'WARNING',
            'title': 'Almacenamiento permaneció sobre su umbral de advertencia',
            'explanation': 'Temperatura sostenida sobre el umbral reportado.',
            'evidence': ['Temperatura máxima: 80 °C'],
        },
        {
            'component': 'GPU:RTX Example', 'status': 'WARNING',
            'title': 'GPU requiere revisión', 'explanation': 'Evidencia real.',
            'evidence': ['Temperatura máxima: 90 °C'],
        },
    ])
    reports = {x['key']: x for x in build_component_assessments(result)}
    assert reports['storage']['status'] == 'WARNING'
    assert reports['gpu']['status'] == 'WARNING'
