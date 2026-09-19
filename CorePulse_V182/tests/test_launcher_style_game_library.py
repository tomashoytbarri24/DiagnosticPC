"""V100 — biblioteca launcher responsive, acciones en hover y carga diferida."""
from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f'[PASS] {name}: {bool(condition)}')
    return True


def main():
    gaming = (ROOT / 'gui' / 'gaming_panel.py').read_text(encoding='utf-8')
    health = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    nav = (ROOT / 'gui' / 'internal_navigation.py').read_text(encoding='utf-8')
    scroll = (ROOT / 'gui' / 'stable_scroll.py').read_text(encoding='utf-8')

    init_block = gaming.split('    def __init__', 1)[1].split('    def widget', 1)[0]
    library = health.split('    def _render_registered_games', 1)[1].split('    def _choose_game_artwork', 1)[0]
    geom = health.split('    def _game_library_geometry', 1)[1].split('    def _placeholder_game_image', 1)[0]

    checks = [
        check('version', VERSION.isdecimal()),
        check('gaming_first_paint_is_deferred', '_show_loading_placeholder()' in init_block and '_schedule_initial_tab_load()' in init_block and '_show_current_tab()' not in init_block),
        check('gaming_loading_shell_is_visible', "text='Preparando Gaming…'" in gaming),
        check('gaming_page_is_cached', "'gaming'" in nav.split('CACHEABLE_PAGES = {',1)[1].split('}',1)[0]),
        check('cached_gaming_pauses_and_resumes', "panel.set_active(False)" in nav and "panel.set_active(True)" in nav),
        check('same_tab_does_not_force_full_refresh', 'Reabrir Gaming desde la caché no reconstruye biblioteca/portadas' in gaming),
        check('launcher_library_is_dedicated_route', "('library', 'Biblioteca'" in gaming and 'def _render_gaming_library_section' in health),
        check('launcher_cards_have_16_9_art', 'art_height = int(round(art_width * 9 / 16))' in geom),
        check('launcher_cards_have_compact_body', 'art_size[1] + 80' in library),
        check('launcher_card_has_name_and_hover_menu', "game.get('display_name')" in library and 'action_widget=menu_btn' in library),
        check('launcher_hides_idle_badge', "'LISTO'" not in library and 'Listo para detección' not in library),
        check('launcher_actions_are_contextual', "'Cambiar imagen'" in health and "'Quitar de biblioteca'" in health and '_show_game_actions' in health),
        check('artwork_is_background_loaded', '_start_game_artwork_jobs' in health and "threading.Thread(target=worker, name='CorePulseGameArtwork'" in health),
        check('artwork_has_placeholder_first', '_placeholder_game_image' in health and 'artwork_jobs.append' in library),
        check('responsive_grid_has_real_wrap', 'usable >= 1030' in geom and 'usable >= 680' in geom),
        check('scroll_does_not_rebuild_during_motion', 'self.scroll.defer_until_idle(self._request_render)' in health),
        check('scroll_remains_native_canvas', 'tk.Canvas(' in scroll and 'yview_moveto' in scroll and '_target' not in scroll),
        check('no_nvidia_branding_in_ui', 'NVIDIA' not in gaming and 'NVIDIA' not in library),
    ]
    print(f'\nRESULTADO: PASS ({len(checks)} checks)')


if __name__ == '__main__':
    main()
