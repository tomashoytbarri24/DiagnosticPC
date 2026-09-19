"""V100 — encabezado contextual de módulos del Centro de Salud."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print(f"[PASS] {name}")


def main():
    panel = (ROOT / "gui" / "health_center_panel.py").read_text(encoding="utf-8")
    check("version", VERSION.isdecimal())
    check("stage", bool(STAGE))
    check("header_button_saved", "self.btn_header_back = self._button(" in panel)
    check("header_hero_saved", "self.header_hero = build_title_block(" in panel)
    check("battery_context_title", "'title': 'Salud de batería'" in panel)
    check("battery_context_eyebrow", "'eyebrow': 'Autonomía y desgaste'" in panel)
    check("context_sync_called_on_tab_change", "self._sync_header_context()" in panel and "def _sync_header_context(self):" in panel)
    check("breadcrumb_arrow_removed", "← Centro de salud" not in panel and "Volver a Centro de salud" in panel)
    check("body_title_skipped_on_detail_views", "if not self._performance_only and self._tab != 'summary':\n            return" in panel)
    print("RESULTADO: PASS (9 checks)")


if __name__ == "__main__":
    main()
