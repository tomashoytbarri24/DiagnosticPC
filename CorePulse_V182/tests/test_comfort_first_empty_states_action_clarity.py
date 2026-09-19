"""V100 — Comfort First Empty States & Action Clarity."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    visuals = (ROOT / 'gui' / 'professional_visuals.py').read_text(encoding='utf-8')
    alerts = (ROOT / 'gui' / 'alert_panel.py').read_text(encoding='utf-8')
    history = (ROOT / 'gui' / 'alert_history_panel.py').read_text(encoding='utf-8')
    trends = (ROOT / 'gui' / 'session_trends_panel.py').read_text(encoding='utf-8')

    check('version', VERSION.isdecimal())
    check('exe_runtime_stage_preserved', bool(STAGE))
    check('shared_empty_state_helper', 'def build_empty_state(' in visuals)
    check('empty_state_supports_action', 'action_text=None' in visuals and 'action_command=None' in visuals)
    check('alert_panel_uses_empty_state', 'build_empty_state' in alerts and 'Todo tranquilo por ahora' in alerts)
    check('alert_observing_state_is_clear', 'Aún no hay una alerta sostenida' in alerts)
    check('history_has_empty_state', 'Aún no hay alertas registradas' in history)
    check('history_zero_label_is_human', "'Sin eventos' if not rows" in history)
    check('trends_has_empty_state', 'Todavía no hay sesiones para comparar' in trends)
    check('trends_chart_empty_message', 'Aún no hay sesiones comparables' in trends)

    print('\nRESULTADO: PASS (10 checks)')


if __name__ == '__main__':
    main()
