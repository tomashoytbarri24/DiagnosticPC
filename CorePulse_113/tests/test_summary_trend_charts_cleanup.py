"""V0.10.2.60w — Summary Trend Charts Cleanup."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    main_py = (ROOT / 'main.py').read_text(encoding='utf-8')
    check('version', VERSION == '103')
    check('stage', STAGE == 'STARTUP_RESPONSIVENESS_SINGLE_LAYOUT_AUTHORITY')
    check('single_trends_header', 'TENDENCIAS DE TELEMETRÍA' in dashboard)
    check('summary_cards_removed', '_chart_summary_row' not in dashboard and '_chart_summary_labels' not in dashboard)
    check('actual_value_not_repeated', 'Actual N/A · Promedio N/A · Pico N/A' not in dashboard)
    check('trend_titles_clean', "'CPU (%)'" in dashboard and "'RAM (%)'" in dashboard and "'GPU (%)'" in dashboard)
    check('current_data_stays_top_cards', "text=f'CPU\\n{cpu_name}'" in dashboard and "text='MEMORIA RAM\\nUso físico del sistema'" in dashboard)
    check('canvas_height_206', 'height=206' in main_py and 'canvas_widget.configure(height=206)' in dashboard)
    check('blitting_preserved', 'self.canvas.blit(self.fig.bbox)' in main_py)
    check('real_data_copy', 'Datos reales · sin duplicar el valor actual' in dashboard)
    print('\nRESULTADO: PASS (10 checks)')


if __name__ == '__main__':
    main()
