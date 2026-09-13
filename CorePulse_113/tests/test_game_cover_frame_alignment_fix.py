"""V100 — alineación limpia del marco visual en Gaming > Biblioteca."""
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
    check('version', VERSION == '103')

    health = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    render = health.split('    def _render_registered_games', 1)[1].split('    def _choose_game_artwork', 1)[0]
    check('art_host_flush_width', "art_host.pack(side='top', fill='x')" in render)
    check('art_host_no_inner_radius', "corner_radius=0" in render)
    check('art_label_transparent', "fg_color='transparent'" in render)

    presentation = (ROOT / 'performance' / 'game_presentation.py').read_text(encoding='utf-8')
    block = presentation.split('def fallback_game_artwork', 1)[1].split('def load_game_artwork', 1)[0]
    check('fallback_no_inner_rounded_rectangle', 'draw.rounded_rectangle' not in block)
    check('fallback_lines_extend_beyond_canvas_for_edge_alignment', 'width + height' in block)
    check('fallback_single_final_rounding', 'return _rounded_rgba(image, (width, height), radius=10)' in block)
    print('\nRESULTADO: PASS (7 checks)')


if __name__ == '__main__':
    main()
