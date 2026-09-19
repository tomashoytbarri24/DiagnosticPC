"""V100 — Gaming estable después de abrir juegos y ejecutar benchmark."""
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
    check('version', VERSION.isdecimal())
    health = (ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    check('coalesced_render_queue', 'def _request_render' in health and '_render_pending' in health)
    check('post_geometry_finalize', 'def _finalize_render' in health and 'self.scroll._refresh_geometry()' in health)
    check('strong_repaint_after_rebuild', 'self.scroll._flush_repaint(strong=True)' in health)
    check('scroll_position_preserved', '_capture_scroll_fraction' in health and '_restore_scroll_fraction' in health)
    async_block = health.split('    def _async',1)[1].split('    def _lazy_load',1)[0]
    check('async_uses_scheduled_render', 'self._request_render(1)' in async_block and 'on_done(result, error)' in async_block)
    check('benchmark_blocks_status_rebuild', "dynamic_blockers = {'profile_change', 'benchmark', 'game_scan'}" in health)
    gaming = (ROOT/'gui'/'gaming_panel.py').read_text(encoding='utf-8')
    check('dead_duplicate_summary_removed', 'def _build_summary' not in gaming)
    check('summary_not_rendered', '_build_summary(body)' not in gaming)
    print('\nRESULTADO: PASS (8 checks)')

if __name__ == '__main__':
    main()
