from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v134_version_and_stage():
    ns = {}
    exec((ROOT / 'core' / 'version.py').read_text(encoding='utf-8'), ns)
    assert str(ns["VERSION"]).isdigit()
    assert bool(ns["STAGE"])


def test_corepulse_diagnostics_source_preserves_real_or_na_contract():
    src = (ROOT / 'core' / 'corepulse_diagnostics.py').read_text(encoding='utf-8')
    assert 'REAL_OR_NA_ONLY' in src
    assert 'collect_readiness' in src
    assert 'build_sensor_diagnostics' in src
    assert 'corepulse_capabilities.json' in src
    # Optional absence must stay N/A rather than becoming an error/score penalty.
    assert 'if required' in src
    assert 'return "N/A"' in src
    ast.parse(src)


def test_health_center_exposes_corepulse_capability_module_without_sidebar_button():
    src = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    assert "'corepulse': self._render_corepulse_diagnostics" in src
    assert "lambda: self._select_tab('corepulse')" in src
    assert 'Actualizar diagnóstico' in src
    assert 'Sensores expuestos por este equipo' in src
    # V134 intentionally does not add another sidebar button and therefore keeps V133 vertical balance.
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'btn_corepulse_diagnostics' not in dashboard
