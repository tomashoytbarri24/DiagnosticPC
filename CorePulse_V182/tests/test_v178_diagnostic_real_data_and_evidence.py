from core.diagnostic_evidence import storage_snapshot
from core.diagnostic_summary import build_component_assessments


def test_storage_snapshot_merges_volume_usage_with_physical_device():
    tele = {'_storage_devices': [{'model': 'NVMe Test', 'temperature_c': 42}], '_storage_health_cache': {}}
    vols = [{'model': 'NVMe Test', 'used_percent': 61, 'total_gb': 1000, 'health': 93, 'health_source': 'SMART'}]
    row = storage_snapshot(tele, vols)[0]
    assert row['used_space_percent'] == 61
    assert row['life_percent'] == 93


def test_diagnostic_keeps_all_three_facets_visible_in_contract():
    result = {
        'statistics': {'cpu': {'usage_percent': {'avg': 4}}, 'ram': {'usage_percent': {'avg': 30}}, 'gpus': {}},
        'findings': [],
        'complete_diagnostic': {
            'platform': 'Linux',
            'hardware': {'storage': [{'model': 'NVMe', 'used_percent': 55}], 'battery': {'present': True, 'health_percent': 90}},
            'benchmark': {'ssd': {'status': 'OK', 'read_mbps': 1000}},
        },
        'audio_test': {'answers': {'left': 'VERIFICADO', 'right': 'NO EVALUADO', 'microphone': 'NO EVALUADO'}},
    }
    reports = {x['key']: x for x in build_component_assessments(result)}
    assert len(reports['storage']['display_facets']) == 3
    assert [x[0] for x in reports['audio']['display_facets']] == ['Izquierdo', 'Derecho', 'Micrófono']


def test_ui_limits_evidence_to_findings():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert "finding_visible = status in {'WARNING', 'CRITICAL'}" in src
    assert "has_evidence_detail = bool(finding_visible" in src


def test_version_authority_remains_valid_after_v178():
    from core.version import VERSION, STAGE
    assert VERSION.isdecimal()
    assert STAGE
