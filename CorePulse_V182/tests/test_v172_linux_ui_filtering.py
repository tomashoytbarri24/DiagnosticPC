from __future__ import annotations

from unittest.mock import patch


def test_linux_readiness_omits_windows_only_capabilities():
    import core.startup_readiness as sr
    with patch.object(sr.platform, 'system', return_value='Linux'):
        report = sr.collect_readiness(version='172')
    ids = {item.id for item in report.items}
    assert 'presentmon' not in ids
    assert 'rtss' not in ids
    assert 'import_wmi' not in ids
    assert 'import_win32api' not in ids
    assert 'import_clr' not in ids


def test_linux_corepulse_diagnostics_does_not_publish_powershell(monkeypatch):
    import core.corepulse_diagnostics as diag
    monkeypatch.setattr(diag.os, 'name', 'posix', raising=False)
    monkeypatch.setattr(diag, 'collect_readiness', lambda version=None: type('R', (), {'items': []})())
    monkeypatch.setattr(diag, 'build_sensor_diagnostics', lambda telemetry: {'groups': [], 'available': 0, 'total': 0})
    report = diag.collect_corepulse_diagnostics({}, persist=False)
    assert 'powershell' not in {item.get('id') for item in report['optional']}


def test_linux_benchmark_component_source_includes_gpu_since_v181():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    text = (root / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    assert "platform.system() in {'Windows', 'Linux'}" in text
    assert "for index, key in enumerate(self._benchmark_available_components())" in text
