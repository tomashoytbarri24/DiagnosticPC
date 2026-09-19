"""Regresión V0.10.2.55w — Health Center UI Polish."""
from __future__ import annotations

from pathlib import Path
import sys
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {bool(cond)}")
    return bool(cond)


def main():
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    results = [
        check('version', VERSION.isdecimal()),
        check('dedicated_health_icon_mapping', "'btn_health_center': 'health.png'" in dashboard and "'btn_health_center': 'diagnostic.png'" not in dashboard),
        check('health_icon_dark_exists', (ROOT / 'assets' / 'sidebar' / 'health.png').exists()),
        check('health_icon_light_exists', (ROOT / 'assets' / 'sidebar_light' / 'health.png').exists()),
        check('single_button_style_authority', 'def _button(' in panel and panel.count('ctk.CTkButton(') == 1),
        check('direct_module_navigation', "uniform='health_center_tabs'" not in panel and "uniform='health_module_cards'" in panel),
        check('health_summary_uses_only_module_grid', "uniform='health_overview'" not in panel and "uniform='health_module_cards'" in panel),
        check('windows_actions_corepulse_style', "uniform='health_windows_actions'" in panel),
        check('technical_state_localized', "'NO_EVIDENCE': 'Sin evidencia'" in panel and "'CONFIRMED': 'Confirmado'" in panel),
        check('reason_localized', "'THERMAL': 'Límite térmico'" in panel),
        check('professional_header_copy', "text='Centro de salud'" in panel and 'Salud del sistema, mantenimiento preventivo y recuperación' in panel),
        check('real_or_na_badge', "Datos reales · REAL_OR_NA" in panel),
    ]
    for rel in ('assets/sidebar/health.png','assets/sidebar_light/health.png'):
        try:
            im = Image.open(ROOT / rel)
            results.append(check(rel + '_64_rgba', im.size == (64,64) and im.mode == 'RGBA'))
        except Exception:
            results.append(check(rel + '_64_rgba', False))
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
