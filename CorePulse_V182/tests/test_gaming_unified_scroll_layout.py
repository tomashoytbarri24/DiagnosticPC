"""V100 — Gaming consolidado con un solo scroll y Overlay separado."""
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
    gaming = (ROOT/'gui'/'gaming_panel.py').read_text(encoding='utf-8')
    health = (ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    results = [
        check('version', VERSION.isdecimal()),
        check('gaming_has_single_main_scroll', 'self.main_scroll = scroll' in gaming and 'StableScrollHost(host, fg_color=BG)' in gaming),
        check('duplicate_summary_removed', 'self._build_summary(body)' not in gaming),
        check('performance_uses_external_scroll', 'external_scroll=scroll' in gaming),
        check('health_supports_external_scroll', 'external_scroll=None' in health and 'self._external_scroll = external_scroll' in health),
        check('no_nested_performance_scroll', 'if self._performance_only and self._external_scroll is not None' in health),
        check('overlay_is_direct_action', "('overlay', 'Overlay'" in gaming and "lambda: self.select_tab('overlay')" in gaming),
        check('overlay_is_separate_cached_view', "if key == 'overlay':" in gaming and 'OverlayConfigPanel(overlay_body, self.app)' in gaming),
        check('overlay_has_scroll_fallback', "self._view_scrolls[key] = scroll" in gaming),
        check('old_visual_tab_bar_removed', 'tabs_wrap =' not in gaming and 'self.tab_buttons' not in gaming),
        check('back_from_overlay_is_explicit', "('home', 'Inicio'" in gaming and "('overlay', 'Overlay'" in gaming),
        check('route_compatibility_preserved', "TABS = (('performance', 'Rendimiento'), ('overlay', 'Overlay'))" in gaming),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
