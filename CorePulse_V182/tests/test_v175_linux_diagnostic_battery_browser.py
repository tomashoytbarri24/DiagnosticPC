from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def _write(path: Path, value):
    path.write_text(str(value), encoding='utf-8')


def test_linux_sysfs_battery_reads_capacity_health_and_electrical_data(tmp_path):
    import core.battery_health as bh
    bat = tmp_path / 'BAT0'
    bat.mkdir()
    _write(bat / 'type', 'Battery')
    _write(bat / 'status', 'Discharging')
    _write(bat / 'charge_full_design', 5000000)  # 5000 mAh
    _write(bat / 'charge_full', 4250000)         # 4250 mAh = 85%
    _write(bat / 'charge_now', 2500000)
    _write(bat / 'voltage_now', 15000000)        # 15 V
    _write(bat / 'current_now', 1200000)          # 1200 mA
    _write(bat / 'capacity', 50)
    _write(bat / 'cycle_count', 321)
    with patch.object(bh.platform, 'system', return_value='Linux'):
        data = bh._linux_sysfs_battery_data(tmp_path)
    assert data['detected'] is True
    assert round(data['health_percent'], 1) == 85.0
    assert round(data['degradation_percent'], 1) == 15.0
    assert round(data['designed_capacity_mah']) == 5000
    assert round(data['full_charge_capacity_mah']) == 4250
    assert round(data['designed_capacity_mwh']) == 75000
    assert round(data['full_charge_capacity_mwh']) == 63750
    assert data['cycle_count'] == 321
    assert data['charge_percent'] == 50
    assert round(data['voltage_v'], 1) == 15.0
    assert round(data['current_ma']) == -1200
    assert data['charge_discharge_rate_w'] < 0


def test_collect_battery_health_prefers_linux_sysfs_without_windows_sources(monkeypatch):
    import core.battery_health as bh
    monkeypatch.setattr(bh.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(bh, 'probe_battery_presence', lambda *a, **k: {'present': True, 'resolved': True, 'source': 'sysfs'})
    monkeypatch.setattr(bh.psutil, 'sensors_battery', lambda: None)
    monkeypatch.setattr(bh, '_linux_sysfs_battery_data', lambda: {
        'detected': True, 'health_percent': 91, 'degradation_percent': 9,
        'designed_capacity_mah': 5000, 'full_charge_capacity_mah': 4550,
        'cycle_count': 100, 'charge_percent': 57, 'voltage_v': 15.2,
        'current_ma': -800, 'charge_discharge_rate_w': -12.16,
        'power_plugged': False, 'source': 'Linux sysfs /sys/class/power_supply',
    })
    monkeypatch.setattr(bh, '_wmi_battery_data', lambda: (_ for _ in ()).throw(AssertionError('WMI no debe ejecutarse')))
    monkeypatch.setattr(bh, '_powercfg_battery_report', lambda: (_ for _ in ()).throw(AssertionError('powercfg no debe ejecutarse')))
    data = bh.collect_battery_health({})
    assert data['present'] is True
    assert data['health_percent'] == 91
    assert data['degradation_percent'] == 9
    assert data['cycle_count'] == 100
    assert data['current_ma'] == -800
    assert any('Linux sysfs' in src for src in data['sources'])


def test_linux_complete_diagnostic_skips_windows_and_runs_gpu_benchmark(monkeypatch):
    import core.complete_diagnostic as diag
    monkeypatch.setattr(diag.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(diag, 'collect_battery_health', lambda telemetry: {'present': True, 'health_percent': 90})
    monkeypatch.setattr(diag, 'storage_snapshot', lambda telemetry, disks: [])
    monkeypatch.setattr(diag, 'automatic_audio_probe', lambda **kwargs: {
        'mode': 'AUTOMATIC_TECHNICAL', 'status': 'AUDIO TÉCNICO OK', 'reason': 'ok',
        'devices': {}, 'technical': {}, 'answers': {}, 'errors': [],
    })
    seen = {}

    def bench(mode, components, **kwargs):
        seen['components'] = tuple(components)
        return {
            'status': 'OK',
            'cpu': {'status': 'OK', 'telemetry': {'during_sample_count': 2, 'cpu_usage': {'samples': 2}}},
            'ram': {'status': 'OK', 'telemetry': {'during_sample_count': 2, 'ram_usage': {'samples': 2}}},
            'ssd': {'status': 'OK', 'telemetry': {'during_sample_count': 0, 'storage_temperature': {'samples': 0}}},
            'gpu': {'status': 'OK', 'telemetry': {'during_sample_count': 2, 'gpu_usage': {'samples': 2}}},
        }
    monkeypatch.setattr(diag, 'run_benchmark_suite', bench)
    base = {'session_valid': True, 'overall_status': 'NORMAL', 'findings': [], 'duration_seconds': 5,
            'adaptive_diagnostic': {'finish_reason': 'ready'}}
    result = diag.run_complete_diagnostic(base, {}, [])
    complete = result['complete_diagnostic']
    assert seen['components'] == ('cpu', 'ram', 'ssd', 'gpu')
    assert complete['platform'] == 'Linux'
    assert 'windows' not in complete
    assert 'windows' not in complete['phases']
    assert 'audio' in complete['phases']
    assert complete['status'] == 'COMPLETE'
    assert result['overall_status'] == 'NORMAL'


def test_linux_component_summary_omits_windows_and_keeps_observed_gpu(monkeypatch):
    import core.diagnostic_summary as summary
    monkeypatch.setattr(summary.platform, 'system', lambda: 'Linux')
    result = {
        'statistics': {'gpus': {'GPU': {
            'usage_percent': {'avg': 10, 'samples': 2},
            'temperature_c': {'avg': 45, 'samples': 2},
        }}},
        'complete_diagnostic': {
            'platform': 'Linux',
            'hardware': {'battery': {'present': False}, 'storage': []},
            'benchmark': {},
        },
    }
    reports = summary.build_component_assessments(result)
    keys = {row['key'] for row in reports}
    assert 'windows' not in keys
    gpu = next(row for row in reports if row['key'] == 'gpu')
    assert gpu['status'] == 'NORMAL'
    benchmark_facet = next(item for item in gpu['facets'] if item[0] == 'Benchmark')
    assert benchmark_facet[1] == 'N/A'


def test_releases_button_uses_platform_foreground_opener():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / 'gui' / 'update_dialog.py').read_text(encoding='utf-8')
    assert 'open_url_foreground(releases_web_url())' in source
    assert 'webbrowser.open(releases_web_url())' not in source
