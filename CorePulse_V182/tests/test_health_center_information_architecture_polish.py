"""V0.10.2.55w — Health Center Information Architecture Polish."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print("[PASS]", name)


def main():
    panel = (ROOT / "gui" / "health_center_panel.py").read_text(encoding="utf-8")
    check("version", VERSION.isdecimal())
    check("exe_runtime_foundation_preserved", bool(STAGE))
    check("summary_tab_still_exists", "('summary', 'Estado general')" in panel)
    check("history_tab_shortened", "('history', 'Historial')" in panel)
    check("purpose_separated_from_monitoring", "sin repetir el monitoreo en vivo" in panel)
    check("overview_removed_for_clarity", "uniform='health_overview'" not in panel)
    check("summary_reduced_to_modules", "def _render_summary(self):" in panel and "def _health_module_card" in panel)
    check("no_synthetic_score_introduced_in_summary", "Índice técnico N/A" not in panel)
    check("review_indicators_removed", "Indicadores para revisar" not in panel)
    check("health_modules_grid", "uniform='health_module_cards'" in panel and "def _health_module_card" in panel)
    check("six_areas", all(label in panel for label in (
        "'Batería'", "'Windows'", "'Reparación'", "'Historial y cambios'", "'Recuperación'", "'Rendimiento'"
    )))
    check("health_quick_actions_removed", "health_quick_actions" not in panel)
    check("gaming_shortcuts_are_isolated", "Accesos rápidos" in panel and "_render_gaming_home_shortcuts" in panel)
    check("unknown_states_preserved", "Sin analizar" in panel and "Sin verificar" in panel and "N/A no se convierten" in panel)
    check("traceability_link_removed_from_summary", "Ver trazabilidad" not in panel)
    check("monitoring_return", "Volver al monitoreo" in panel)
    print("\nRESULTADO: PASS (16 checks)")


if __name__ == "__main__":
    main()
