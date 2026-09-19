"""V100 — Gaming Information Architecture Reduction."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    gaming = (ROOT / 'gui' / 'gaming_panel.py').read_text(encoding='utf-8')
    check('version', VERSION.isdecimal())
    check('exe_runtime_foundation_preserved', bool(STAGE))
    check('gaming_home_section_state', "self._performance_section = 'home'" in panel)
    check('gaming_section_navigation', 'def _render_gaming_section_nav' in panel)
    check('dedicated_library_section', 'def _render_gaming_library_section' in panel)
    check('dedicated_stability_section', 'def _render_gaming_stability_section' in panel)
    check('dedicated_benchmark_section', 'def _render_gaming_benchmark_section' in panel)
    check('home_shortcuts_present', 'Accesos rápidos' in panel)
    check('main_view_no_forced_library', 'self._render_gaming_comfort_home()' in panel and "section == 'library'" in panel)
    check('hero_subtitle_simplified', 'vistas dedicadas' in gaming)
    print('\nRESULTADO: PASS (10 checks)')


if __name__ == '__main__':
    main()
