"""V100 — Gaming Comfort First Hub."""
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
    check('version', VERSION == '103')
    check('stage_preserved', STAGE == 'STARTUP_RESPONSIVENESS_SINGLE_LAYOUT_AUTHORITY')
    check('comfort_home_renderer', 'def _render_gaming_comfort_home' in panel)
    check('main_home_routes_to_comfort', 'self._render_gaming_comfort_home()' in panel)
    check('compact_modes', "uniform='gaming_profile_choices'" in panel)
    check('boost_config_is_dedicated', "_select_performance_section('boost')" in panel and 'def _render_game_boost_config_section' in panel)
    check('detail_back_navigation', "back_text='Volver a Inicio'" in panel)
    check('tools_are_lazy', "('library', 'Biblioteca'" in gaming and "('stability', 'Estabilidad'" in gaming and "Benchmark rápido" in panel)
    check('hero_copy_is_comfort_first', 'Juego actual, perfil y estado del equipo en una sola vista' in gaming)
    check('overlay_stays_separate', 'Overlay In-Game' in gaming)
    print('\nRESULTADO: PASS (10 checks)')


if __name__ == '__main__':
    main()
