"""V113 — artwork multi-launcher, eliminación y cards uniformes."""
from pathlib import Path
import os, tempfile, json
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    presentation = (ROOT / 'performance' / 'game_presentation.py').read_text(encoding='utf-8')
    detector = (ROOT / 'performance' / 'game_detector.py').read_text(encoding='utf-8')
    ui = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    check('epic_riot_cache_url_resolution', '_artwork_urls_from_blob' in presentation and '_download_official_artwork' in presentation)
    check('official_hosts_are_allowlisted', "'epic':" in presentation and "'riot':" in presentation)
    check('nvidia_title_matching_strengthened', 'title_hint=title_hint' in presentation and 'if score >= 60' in presentation)
    check('riot_source_is_first_class', "return f'RIOT|{inferred}'" in detector and "source, game_id, install_root = 'RIOT'" in detector)
    check('detected_game_removal_supported', 'def remove_game_from_library' in detector and "excluded.add(exe)" in detector)
    check('visible_remove_button', "name_row, 'Eliminar'" in ui and '_remove_game_from_library(g)' in ui)
    check('cards_use_uniform_grid', "uniform='game_library_cards'" in ui and 'card.grid(row=row, column=col' in ui)
    check('third_card_not_pack_clipped', "row_inner.pack(anchor='w')" not in ui)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
