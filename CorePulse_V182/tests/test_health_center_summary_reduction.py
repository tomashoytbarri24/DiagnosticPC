"""Regresión heredada de Health Center Summary Reduction, preservada en V100."""
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
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('duplicate_summary_title_removed', "'Áreas de salud'" not in panel)
    check('summary_intro_removed', 'Abre sólo el módulo que necesites.' not in panel and 'Los estados “Sin analizar”, “Sin verificar” y N/A no se convierten en resultados normales.' not in panel)
    check('module_grid_preserved', "uniform='health_module_cards'" in panel)
    check('overview_removed', "uniform='health_overview'" not in panel)
    check('review_indicators_removed', 'Indicadores para revisar' not in panel)
    check('traceability_shortcut_removed_from_summary', 'Ver trazabilidad' not in panel)
    check('summary_footer_removed', 'Centro de salud interpreta y organiza evidencia; el monitoreo en vivo permanece en Resumen.' not in panel)
    check('all_modules_preserved', all(label in panel for label in (
        "'Batería'", "'Windows'", "'Reparación'", "'Historial y cambios'", "'Recuperación'", "'Rendimiento'"
    )))
    print('\nRESULTADO: PASS')


if __name__ == '__main__':
    main()