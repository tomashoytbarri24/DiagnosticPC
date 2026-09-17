"""Regresión funcional de Professional Visual System Polish V0.10.2.55w."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    visuals = (ROOT / 'gui' / 'professional_visuals.py').read_text(encoding='utf-8')
    render = (ROOT / 'gui' / 'render_polish.py').read_text(encoding='utf-8')
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    gaming = (ROOT / 'gui' / 'gaming_panel.py').read_text(encoding='utf-8')
    network = (ROOT / 'gui' / 'network_detail_panel.py').read_text(encoding='utf-8')
    tweaks = (ROOT / 'gui' / 'windows_tweaks_panel.py').read_text(encoding='utf-8')
    telemetry = (ROOT / 'gui' / 'telemetry_detail_panel.py').read_text(encoding='utf-8')
    diagnostic = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')

    results = [
        check('version', VERSION == '103'),
        check('stage', STAGE == 'STARTUP_RESPONSIVENESS_SINGLE_LAYOUT_AUTHORITY'),
        check('shared_helper_exists', 'def build_title_block' in visuals and 'def build_badge_row' in visuals),
        check('global_polish_constants', 'GLOBAL_CARD_RADIUS = 12' in render and 'GLOBAL_INPUT_RADIUS = 8' in render),
        check('dashboard_identity_cards', "eyebrow='Salud del sistema'" in dashboard and "eyebrow='Trazabilidad'" in dashboard),
        check('agent_realtime_badge', "text='Tiempo real'" in layout and 'app._agent_badge = badge' in layout),
        check('gaming_header_is_clean', "text='Gaming'" in gaming and "('home', 'Inicio'" in gaming and 'Vista simplificada' not in gaming),
        check('network_header_uses_helper', 'build_title_block(' in network and "eyebrow='Conectividad avanzada'" in network),
        check('tweaks_header_uses_helper', 'build_title_block(' in tweaks and "eyebrow='Windows 11 · Ajustes seguros'" in tweaks),
        check('telemetry_header_uses_helper', 'build_title_block(' in telemetry and "eyebrow='Evidencia certificada'" in telemetry),
        check('diagnostic_header_uses_helper', 'build_title_block(' in diagnostic and "eyebrow='Diagnóstico certificado'" in diagnostic),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
