"""V100 — cards de biblioteca robustas dentro de scroll nativo."""
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
    print(f'[PASS] {name}')


def main():
    health = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    block = health.split('    def _render_registered_games', 1)[1].split('    def _choose_game_artwork', 1)[0]
    geom = health.split('    def _game_library_geometry', 1)[1].split('    def _placeholder_game_image', 1)[0]
    placeholder = health.split('    def _placeholder_game_image', 1)[1].split('    def _bind_game_card_hover', 1)[0]

    check('version', VERSION.isdecimal())
    check('rows_are_real_widgets', "row_frame.pack(fill='x'" in block and "card.pack(side='left'" in block)
    check('card_does_not_use_grid_for_structure', 'card.grid(' not in block and 'grid.grid_columnconfigure' not in block)
    check('no_absolute_art_or_footer_layout', 'art_label.place(' not in block and 'footer.place(' not in block)
    check('fixed_card_without_child_geometry_race', 'card.pack_propagate(False)' in block and "body.pack(side='bottom', fill='both', expand=True)" in block)
    check('name_always_has_fallback', "visible_name = str(game.get('display_name') or '').strip()" in block and "visible_name = visible_name or 'Juego'" in block)
    check('name_row_uses_pack', "name.pack(side='left', fill='x', expand=True" in block)
    check('menu_is_hover_revealed', 'Intencionalmente NO se empaqueta aquí' in block and 'action_widget=menu_btn' in block)
    check('art_is_still_16_9', 'art_height = int(round(art_width * 9 / 16))' in geom)
    check('placeholder_is_not_diagonal_wallpaper', 'fallback_game_icon' in placeholder and 'for x in range(' not in placeholder)
    check('artwork_remains_async', '_start_game_artwork_jobs(artwork_jobs, generation)' in block)
    print('\nRESULTADO: PASS (11 checks)')


if __name__ == '__main__':
    main()
