"""V100 — Análisis de Windows separado por vistas internas."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print(f"[PASS] {name}")


def main():
    ui = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    render = ui[ui.index('    def _render_windows(self):'):ui.index('    def _render_analyzer(self, title, data, kind):')]
    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('section_state', "self._windows_section = 'summary'" in ui)
    check('section_switcher', 'def _set_windows_section(self, section):' in ui)
    check('windows_entry_resets_to_summary', "if key == 'windows' and previous != 'windows':" in ui and "self._windows_section = 'summary'" in ui)
    check('internal_nav', "('summary', 'Resumen')" in ui and "('services', 'Servicios')" in ui and "('crashes', 'Estabilidad')" in ui and "('drivers', 'Controladores')" in ui)
    check('summary_grid', 'def _render_windows_summary(self):' in ui and "text='Elige qué quieres revisar'" in ui)
    check('single_detail_dispatch', "if section == 'summary':" in render and "config = {" in render)
    check('no_monolithic_four_analyzers', "self._render_analyzer('Inicio',self._startup,'startup')" not in render and "self._render_analyzer('Servicios',self._services,'services')" not in render)
    check('service_and_stability_pagination_preserved', '_services_page_size = 40' in ui and '_stability_page_size = 25' in ui)
    check('header_copy_is_modular', 'Revisa inicio, servicios, estabilidad y controladores por separado' in ui)
    print('RESULTADO: PASS (11 checks)')


if __name__ == '__main__':
    main()
