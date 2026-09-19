"""V100 — centrado responsive de filas en Gaming > Biblioteca."""
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

    check('version', VERSION.isdecimal())
    check('outer_row_fills_viewport', "row_frame.pack(fill='x', pady=(0, gap))" in block)
    check('launcher_rows_are_left_aligned', "row_inner.pack(anchor='w')" in block)
    check('cards_live_inside_launcher_holder', 'row_inner, width=card_width' in block)
    check('last_card_has_no_trailing_gap', '0 if is_row_end else gap' in block)
    check('no_structural_place_regression', 'art_label.place(' not in block and 'footer.place(' not in block)
    check('launcher_cards_remain_16_9', 'art_height = int(round(art_width * 9 / 16))' in geom)
    check('responsive_columns_remain_bounded', 'usable >= 1030' in geom and 'usable >= 680' in geom and 'columns = 1' in geom)
    check('artwork_remains_async', '_start_game_artwork_jobs(artwork_jobs, generation)' in block)
    print('\nRESULTADO: PASS (9 checks)')


if __name__ == '__main__':
    main()
