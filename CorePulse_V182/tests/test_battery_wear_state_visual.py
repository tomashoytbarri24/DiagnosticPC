"""V100 — desgaste vertical con contenido centrado, estado breve y sin barra falsa."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.version import VERSION

def test_visual_contract():
    panel = (ROOT / "gui" / "health_center_panel.py").read_text(encoding="utf-8")
    start = panel.index("    def _battery_wear_visual")
    end = panel.index("    def _health_tone", start)
    helpers = panel[start:end]
    render_start = panel.index("    def _render_battery(self):")
    render_end = panel.index("    def _render_performance(self):", render_start)
    render = panel[render_start:render_end]

    checks = {
        "version": VERSION.isdecimal(),
        "wear_helper": "def _battery_wear_card" in helpers,
        "wear_spans_two_rows": "rowspan=2" in helpers,
        "wear_large_value": "font=(FONT, 31, 'bold')" in helpers,
        "wear_state_helper": "def _battery_wear_state_label" in helpers,
        "wear_state_low": "return 'Bajo'" in helpers,
        "wear_state_mid": "return 'Moderado'" in helpers,
        "wear_state_high": "return 'Alto'" in helpers,
        "wear_content_frame": "content = ctk.CTkFrame(card, fg_color='transparent')" in helpers,
        "wear_centered_value": "anchor='center'" in helpers,
        "wear_balanced_rows": "content.grid_rowconfigure(0, weight=1)" in helpers and "content.grid_rowconfigure(3, weight=1)" in helpers,
        "wear_no_progress_bar": "CTkProgressBar" not in helpers,
        "wear_no_accent_line": "height=3" not in helpers and "height=5" not in helpers,
        "wear_color_low": "if value < 20.0" in helpers and "return GREEN" in helpers,
        "wear_color_mid": "if value < 35.0" in helpers and "return AMBER" in helpers,
        "wear_color_high": "return RED" in helpers,
        "wear_na_muted": "return MUTED" in helpers,
        "render_uses_dedicated_card": "self._battery_wear_card(details, 0, 3, b.get('degradation_percent'))" in render,
        "wear_removed_from_generic_specs": "('Desgaste', _fmt" not in render,
    }

    failed = [name for name, ok in checks.items() if not ok]
    assert not failed, f"Failed: {', '.join(failed)}"


if __name__ == '__main__':
    test_visual_contract()
    print('RESULTADO: PASS')
