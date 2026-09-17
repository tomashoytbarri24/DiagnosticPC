"""V0.10.2.60w — Gaming Header Navigation Cleanup."""
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
    gaming = (ROOT/'gui'/'gaming_panel.py').read_text(encoding='utf-8')
    health = (ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    check('version', VERSION == '103')
    check('stage_preserved', STAGE == 'STARTUP_RESPONSIVENESS_SINGLE_LAYOUT_AUTHORITY')
    check('single_clean_title', "text='Gaming'" in gaming)
    check('old_eyebrow_removed', "eyebrow='Gaming hub profesional'" not in gaming)
    check('old_badges_removed', 'Vista simplificada' not in gaming)
    check('top_nav_present', all(x in gaming for x in ("('home', 'Inicio'", "('library', 'Biblioteca'", "('stability', 'Estabilidad'", "('overlay', 'Overlay'")))
    check('duplicate_overlay_button_removed', "header, 'Overlay In-Game'" not in gaming and "text='Overlay In-Game'" not in gaming)
    check('section_router_present', 'def select_section(self, section):' in gaming)
    check('library_duplicate_header_removed', "_render_gaming_detail_header('Biblioteca'" not in health)
    check('advanced_return_is_contextual', "back_text='Volver a Inicio'" in health and "back_text='Volver a Estabilidad'" in health)
    print('\nRESULTADO: PASS (10 checks)')

if __name__ == '__main__':
    main()
