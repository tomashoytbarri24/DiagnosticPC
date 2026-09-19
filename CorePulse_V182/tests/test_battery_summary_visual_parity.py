"""V100 — batería usa jerarquía visual del Resumen sin inventar métricas."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.version import VERSION

def test_visual_contract():
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    start = panel.index('    def _render_battery(self):')
    end = panel.index('    def _render_performance(self):', start)
    battery = panel[start:end]

    checks = {
        'version': VERSION.isdecimal(),
        'summary_card_helper': 'def _battery_summary_card' in panel,
        'detail_card_helper': 'def _battery_detail_card' in panel,
        'four_primary_cards': all(x in battery for x in ("'Salud'", "'Carga'", "'Ciclos'", "'Autonomía'")),
        'summary_visual_value': "font=(FONT, 26, 'bold')" in panel and 'text_color=TEXT' in panel,
        'real_health_progress': "progress=(health / 100.0) if health is not None else None" in battery,
        'real_charge_progress': "progress=(charge / 100.0) if charge is not None else None" in battery,
        'no_cycle_fake_progress': "primary, 2, 'Ciclos'" in battery and "primary, 3, 'Autonomía'" in battery,
        'detail_grid': "'DETALLES DE BATERÍA'" in battery and 'first_row = (' in battery and 'second_row = (' in battery,
        'all_detail_metrics': all(x in battery for x in (
            "'Capacidad de diseño'", "'Carga completa'", "'Capacidad restante'",
            "'Voltaje'", "'Corriente'", "'Carga / descarga'"
        )),
        'derived_current_traceability': 'Calculada desde Rate/Voltage reales' in battery,
        'sources_visible': "'FUENTE DE LOS DATOS'" in battery and '_source_label' in battery,
        'desktop_aware_kept': "if not b.get('present')" in battery,
        'real_or_na_formatting': '_fmt(' in battery and "else 'N/A'" in battery,
    }

    failed = [name for name, ok in checks.items() if not ok]
    assert not failed, f"Failed: {', '.join(failed)}"


if __name__ == '__main__':
    test_visual_contract()
    print('RESULTADO: PASS')
