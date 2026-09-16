"""V113 — Resumen: gráficos limpios sin cabecera redundante."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    main_py = (ROOT / 'main.py').read_text(encoding='utf-8')

    check('redundant_header_removed', 'TENDENCIAS DE TELEMETRÍA' not in dashboard)
    check('redundant_subtitle_removed', 'Evolución de uso durante los últimos 60 segundos' not in dashboard)
    check('redundant_real_data_copy_removed', 'Datos reales · sin duplicar el valor actual' not in dashboard)
    check('header_builder_removed', '_ensure_trend_header' not in dashboard)
    check('no_header_height_reservation', '_trend_header' not in layout and 'header_h' not in layout)
    check('balanced_subplot_geometry', 'top=0.86, bottom=0.20, wspace=0.18' in layout and 'top=0.86, bottom=0.20, wspace=0.18' in main_py)
    check('canvas_uses_card_space', 'inner_h = int(frame.winfo_height()) - 20' in layout)
    check('three_metric_titles_preserved', all(token in dashboard for token in ("'CPU (%)'", "'RAM (%)'", "'GPU (%)'")))
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
