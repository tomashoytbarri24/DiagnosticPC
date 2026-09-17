"""Regresión funcional de Network Information Architecture Split V100."""
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
    panel = (ROOT / 'gui' / 'network_detail_panel.py').read_text(encoding='utf-8')
    results = [
        check('version', VERSION == '103'),
        check('stage', STAGE == 'EXE_RUNTIME_INTEGRITY'),
        check('split_buttons_present', "('network', 'Red')" in panel and "('connectivity', 'Conectividad')" in panel),
        check('switch_explanatory_hint', 'Red concentra adaptadores, IP y tráfico real.' in panel and 'Conectividad reúne speed test y diagnóstico activo.' in panel),
        check('view_frames_present', "self._network_view_frames['network'] = network_frame" in panel and "self._network_view_frames['connectivity'] = connectivity_frame" in panel),
        check('switch_method_present', 'def _select_network_view(self, key):' in panel and 'def _refresh_network_view_buttons(self):' in panel),
        check('red_holds_inventory', 'CONEXIÓN ACTIVA' in panel and 'CONTADORES DE TRÁFICO' in panel and 'ADAPTADORES DETECTADOS' in panel),
        check('connectivity_holds_tests', 'SPEED TEST · PRUEBA DE VELOCIDAD DE INTERNET' in panel and 'DIAGNÓSTICO DE CONECTIVIDAD' in panel),
        check('footer_not_lost', 'CorePulse muestra datos reales o N/A: inventario de red' in panel),
        check('back_button_preserved', "text='Volver al monitoreo'" in panel),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
