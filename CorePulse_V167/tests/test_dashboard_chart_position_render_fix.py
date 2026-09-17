"""V0.10.2.60w — storage viewport no puede empujar los gráficos hacia abajo."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    main_py = (ROOT / 'main.py').read_text(encoding='utf-8')
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')

    checks = [
        check('version', VERSION == '103'),
        check(
            'storage_viewport_grid_propagation_locked_at_creation',
            'self.scroll_disks.grid_propagate(False)' in main_py,
        ),
        check(
            'storage_viewport_grid_propagation_locked_on_reflow',
            'app.scroll_disks.grid_propagate(False)' in layout,
        ),
        check(
            'storage_viewport_grid_propagation_locked_on_rebuild',
            'app.scroll_disks.grid_propagate(False)' in dashboard,
        ),
        check(
            'storage_pack_never_expands_vertical_space',
            "self.scroll_disks.pack(fill='x', expand=False" not in main_py
            and "app.scroll_disks.pack(fill='x', expand=False" in dashboard,
        ),
        check(
            'chart_card_still_top_anchored',
            "self.frame_charts.pack(fill='x', expand=False, pady=(6, 0))" not in main_py
            and "app.frame_charts.pack(fill='x', expand=False, pady=(6, 0))" in dashboard,
        ),
        check(
            'responsive_storage_height_has_explicit_authority',
            'target_h = _storage_height_for(app, mode)' in layout
            and "_cfg(getattr(app, 'scroll_disks', None), height=target_h)" in layout,
        ),
        check(
            'percentage_scale_preserved',
            'ax.set_ylim(0, 100)' in main_py,
        ),
        check(
            'drag_scroll_engine_preserved',
            'class StableScrollHost' in (ROOT / 'gui' / 'stable_scroll.py').read_text(encoding='utf-8'),
        ),
    ]

    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
