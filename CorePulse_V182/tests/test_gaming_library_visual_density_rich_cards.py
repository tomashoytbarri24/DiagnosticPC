"""V0.10.2.60w — Gaming Library Visual Density & Rich Cards."""
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
    ui = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    block = ui.split('    def _render_registered_games', 1)[1].split('    def _choose_game_artwork', 1)[0]
    library = ui.split('    def _render_gaming_library_section', 1)[1].split('    def _benchmark_tone_color', 1)[0]
    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('library_filter_state', "self._game_library_filter = 'all'" in ui)
    check('overview_stats', "f'{total} juego'" in library and "en ejecución" in library and "manual" in library)
    check('filters', all(label in library for label in ("'Todos'", "'Detectados'", "'Manuales'", "'En ejecución'")))
    check('no_duplicate_library_heading', "text='Biblioteca', font=(FONT, 17" not in library)
    check('richer_cards', 'height=art_size[1] + 80' in block and "text=kind_text" in block and "text=state_text" in block)
    check('left_aligned_launcher_grid', "row_inner.pack(anchor='w')" in block)
    check('async_artwork_preserved', '_start_game_artwork_jobs(artwork_jobs, generation)' in block)
    check('real_catalog_only', 'registered_games(active_games)' in library and 'registered_games(active_games)' in block)
    check('empty_state_ctas', "'Buscar juegos'" in block and "'+ Agregar juego'" in block)
    print('\nRESULTADO: PASS')


if __name__ == '__main__':
    main()
