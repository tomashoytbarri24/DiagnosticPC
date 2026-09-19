"""V100 — Health Center Direct Module Navigation Polish."""
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
    check("startup_stage_preserved", bool(STAGE))
    check("redundant_horizontal_tabs_removed",
          "uniform='health_center_tabs'" not in panel and
          "tabs = ctk.CTkFrame(self.frame" not in panel)
    check("module_cards_remain_primary_navigation",
          "uniform='health_module_cards'" in panel and
          "lambda: self._select_tab('battery')" in panel and
          "lambda: self._select_tab('windows')" in panel and
          "lambda: self._select_tab('repair')" in panel and
          "lambda: self._select_tab('history')" in panel and
          "lambda: self._select_tab('recovery')" in panel)
    check("detail_views_use_contextual_header_back",
          "'button_text': 'Volver a Centro de salud'" in panel and "self.btn_header_back = self._button(" in panel)
    check("detail_views_have_no_internal_duplicate_back",
          "if not self._performance_only and self._tab != 'summary':\n            return" in panel)
    check("header_return_is_contextual",
          "'Volver al monitoreo'" in panel and "'button_text': 'Volver a Centro de salud'" in panel)
    check("real_or_na_badge_preserved", "Datos reales · REAL_OR_NA" in panel)
    check("health_authority_preserved",
          "current_live_health" in panel and "Evidencia aún no consolidada" in panel)
    check("six_health_areas_preserved",
          all(x in panel for x in (
              "'Batería'", "'Windows'", "'Reparación'",
              "'Historial y cambios'", "'Recuperación'", "'Rendimiento'"
          )))

    print("\nRESULTADO: PASS (10 checks)")


if __name__ == "__main__":
    main()
