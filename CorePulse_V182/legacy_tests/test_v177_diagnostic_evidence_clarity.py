from __future__ import annotations


def _base_result():
    return {
        'statistics': {
            'cpu': {'usage_percent': {'avg': 4, 'samples': 3}},
            'ram': {'usage_percent': {'avg': 30, 'samples': 3}},
            'gpus': {'GPU': {'usage_percent': {'avg': 2, 'samples': 3}, 'temperature_c': {'avg': 40, 'samples': 3}}},
        },
        'findings': [],
        'complete_diagnostic': {
            'platform': 'Linux',
            'hardware': {
                'storage': [{'name': 'NVMe', 'temperature_c': 42}],
                'battery': {'present': True, 'health_percent': 88},
            },
            'benchmark': {
                'ssd': {'status': 'OK', 'read_mbps': 1200, 'path_root': '/'},
            },
        },
        'audio_test': {'answers': {'left': 'VERIFICADO', 'right': 'NO EVALUADO', 'microphone': 'NO EVALUADO'}},
    }


def test_display_facets_drop_na_but_raw_facets_remain():
    from core.diagnostic_summary import build_component_assessments
    reports = build_component_assessments(_base_result())
    storage = next(x for x in reports if x['key'] == 'storage')
    assert len(storage['facets']) == 3
    assert all(str(row[1]).upper() != 'N/A' for row in storage['display_facets'])
    assert any(row[0] == 'Benchmark' for row in storage['display_facets'])


def test_audio_partial_only_shows_real_answer():
    from core.diagnostic_summary import build_component_assessments
    reports = build_component_assessments(_base_result())
    audio = next(x for x in reports if x['key'] == 'audio')
    assert [row[0] for row in audio['display_facets']] == ['Izquierdo']


def test_component_evidence_filters_na_rows_and_reports_availability():
    from core.diagnostic_summary import build_component_evidence
    detail = build_component_evidence(_base_result(), 'storage')
    assert detail['has_evidence'] is True
    values = [str(row.get('value')) for section in detail['sections'] for row in section.get('rows', [])]
    assert values
    assert all(value.upper() not in {'N/A', 'NO EVALUADO', 'SIN SENSOR'} for value in values)


def test_diagnostic_ui_only_opens_evidence_when_available():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    src = (root / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert "if not sections:" in src
    assert "has_evidence_detail = bool(detail.get('has_evidence') or detail.get('sections'))" in src
    assert "refs['evidence_action'].grid_remove()" in src
    assert "badge_text = 'PARCIAL' if has_partial_data else 'SIN DATOS'" in src


def test_version_177_is_authoritative():
    from core.version import VERSION, STAGE
    assert VERSION == '177'
    assert STAGE == 'DIAGNOSTIC_EVIDENCE_CLARITY'
