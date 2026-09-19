"""Regresión funcional de Windows Analysis Table Presentation Polish V100."""
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
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    results = [
        check('version', VERSION.isdecimal()),
        check('stage', bool(STAGE)),
        check('table_helper_present', 'def _render_compact_table(self, parent, columns, rows, empty_text):' in panel),
        check('startup_table', "{'title': 'Elemento'" in panel and "{'title': 'Ubicación'" in panel),
        check('services_table', "{'title': 'Servicio'" in panel and "{'title': 'Carga'" in panel),
        check('crashes_table', "{'title': 'Qué ocurrió'" in panel and "{'title': 'Aplicación / componente'" in panel and "{'title': 'Fuente de Windows'" in panel and "{'title': 'Detalle'" in panel),
        check('drivers_table', "{'title': 'Dispositivo'" in panel and "{'title': 'Proveedor'" in panel),
        check('enumeration_column', "{'title': '#', 'weight': 1" in panel),
        check('no_startup_bullet_render', "Impacto {_impact_label(x.get('impact'))}" not in panel),
        check('health_windows_title_preserved', "self._title('Análisis de Windows'" in panel),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
