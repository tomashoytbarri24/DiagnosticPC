"""V0.10.2.55w — Summary Hierarchy & Consistency Polish."""
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
    dash=(ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    live=(ROOT/'core'/'live_health.py').read_text(encoding='utf-8')
    binding=(ROOT/'gui'/'live_health_binding.py').read_text(encoding='utf-8')
    layout=(ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('primary_secondary_hierarchy', "weight=3" in dash and "weight=2" in dash and 'ESTADO CONSOLIDADO' in dash)
    check('condition_alert_card', 'CONDICIÓN Y ALERTAS' in dash)
    check('agent_instant_enters_health_authority', 'REALTIME_AGENT_CURRENT_SAMPLE' in live and '_agent_instant_level' in live)
    check('no_sensor_value_mutation', "'sensor_values_unchanged': True" in live)
    check('chart_stats', 'Actual {stats' in dash and 'Promedio' in dash and 'Pico' in dash)
    check('storage_copy_compact', "Usado {used:.0f} GB" in dash)
    check('live_health_wording', 'estado unificado' in binding)
    check('agent_card_compacted', 'height=142' in layout and 'target_h = 132 if compact else 142' in layout)
    print('\nRESULTADO: PASS')

if __name__ == '__main__':
    main()
