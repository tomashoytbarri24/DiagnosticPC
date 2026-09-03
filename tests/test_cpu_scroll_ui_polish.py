"""Regresión de estabilidad de scroll migrada a la infraestructura global V0.10.0.0w."""
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
    panel = (ROOT / 'gui' / 'cpu_detail_panel.py').read_text(encoding='utf-8')
    scroll = (ROOT / 'gui' / 'stable_scroll.py').read_text(encoding='utf-8')
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    results = [
        check('version', VERSION == '0.10.0.0w'),
        check('stage', STAGE == 'HEALTH_INTELLIGENCE_RECOVERY'),
        check('cpu_uses_shared_scroll_host', 'StableScrollHost' in panel and 'self.body_scroll.content' in panel),
        check('no_private_ctk_canvas_dependency', "getattr(self.body, '_parent_canvas'" not in panel),
        check('scroll_coalesces_scrollregion', '_schedule_scrollregion' in scroll and '_refresh_scrollregion' in scroll),
        check('scroll_has_inertia_guard', 'is_scrolling' in scroll and '_scroll_active_until' in scroll),
        check('scroll_has_idle_defer', 'defer_until_idle' in scroll),
        check('back_button_has_no_arrow', "text='Volver al resumen'" in panel and '← Volver' not in panel),
        check('dashboard_details_is_real_button', "app._cpu_details_button = ctk.CTkButton" in dashboard and "text='Ver detalles'" in dashboard),
        check('dashboard_details_has_no_arrow', 'Ver detalles  →' not in dashboard and 'Ver detalles →' not in dashboard),
        check('real_or_na_preserved', 'CorePulse muestra datos reales o N/A' in panel),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
