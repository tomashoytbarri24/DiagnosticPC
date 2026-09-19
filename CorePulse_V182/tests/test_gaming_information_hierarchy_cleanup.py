"""V100 — Gaming sin estados duplicados ni títulos redundantes."""
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
    gaming = (ROOT / 'gui' / 'gaming_panel.py').read_text(encoding='utf-8')
    perf = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')

    check('version', VERSION.isdecimal())
    check('top_duplicate_summary_not_rendered', 'self._build_summary(body)' not in gaming)
    check('header_ready_badge_removed', 'Gaming listo' not in gaming and 'self.session_badge' not in gaming)
    check('performance_title_not_repeated_in_gaming', "if not self._performance_only:" in perf and "'Rendimiento Gaming' if" not in perf)
    check('single_session_module_remains', "text='Estado de la sesión'" in perf)
    check('session_header_ready_badge_removed', "state_text = 'JUGANDO'" not in perf)
    check('active_game_is_human_readable', "('JUEGO ACTIVO', active_game_text" in perf)
    check('numeric_games_duplicate_removed', "'JUEGOS ACTIVOS'" not in perf)
    check('windows_plan_and_corepulse_mode_remain_distinct', "'MODO COREPULSE'" in perf and "'PLAN DE WINDOWS'" in perf)
    check('overlay_remains_separate_action', "('overlay', 'Overlay'" in gaming and "select_tab('overlay')" in gaming)
    print('\nRESULTADO: PASS (10 checks)')


if __name__ == '__main__':
    main()
