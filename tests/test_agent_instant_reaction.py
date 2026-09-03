"""Regresión V0.10.0.0w: el agente debe reaccionar a la condición instantánea sin falsear persistencia."""
from __future__ import annotations
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from core.agent_reaction import instant_health_from_sample
from core.agent_reaction import agent_display_state


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    critical = instant_health_from_sample({
        'timestamp': 1.0,
        'cpu_temp': 96.0,
        'cpu_tjmax_distance': 4.0,
        'gpu_temp': 45.0,
    })
    warning = instant_health_from_sample({
        'timestamp': 2.0,
        'cpu_temp': 91.0,
        'cpu_tjmax_distance': 8.0,
        'gpu_temp': 45.0,
    })
    normal = instant_health_from_sample({
        'timestamp': 3.0,
        'cpu_temp': 65.0,
        'cpu_tjmax_distance': 35.0,
        'gpu_temp': 45.0,
    })
    state_base = {
        'mode': 'DESKTOP',
        'overall': 'NORMAL',
        'alerts': {'active': []},
    }
    critical_display = agent_display_state({**state_base, 'instant': critical}, alive=True)
    warning_display = agent_display_state({**state_base, 'instant': warning}, alive=True)
    normal_display = agent_display_state({**state_base, 'instant': normal}, alive=True)
    sustained = agent_display_state({
        **state_base,
        'overall': 'WARNING',
        'instant': critical,
        'alerts': {'active': [{'level': 'WARNING', 'title': 'CPU muy cerca de TjMax de forma sostenida'}]},
    }, alive=True)
    results = [
        check('version', VERSION == '0.10.0.0w'),
        check('instant_critical_uses_real_policy', critical.get('severity') == 'CRITICAL' and 'CPU' in ' '.join(critical.get('reasons') or [])),
        check('instant_warning_uses_real_policy', warning.get('severity') == 'WARNING'),
        check('instant_normal_stays_normal', normal.get('severity') == 'NORMAL'),
        check('agent_reacts_to_critical_immediately', critical_display.get('status') == 'REACCIONANDO' and critical_display.get('label') == 'CRÍTICA INSTANTÁNEA' and critical_display.get('prefix') == 'CONDICIÓN'),
        check('agent_observes_warning_immediately', warning_display.get('status') == 'OBSERVANDO' and warning_display.get('label') == 'ADVERTENCIA INSTANTÁNEA'),
        check('agent_normal_remains_monitoring', normal_display.get('status') == 'MONITOREANDO' and normal_display.get('label') == 'NINGUNA SOSTENIDA'),
        check('sustained_alert_has_priority', sustained.get('label') == 'ADVERTENCIA SOSTENIDA' and sustained.get('prefix') == 'ALERTAS'),
        check('critical_is_not_misrepresented_as_sustained', 'SOSTENIDA' not in critical_display.get('label', '')),
        check('instant_state_is_real_only', critical.get('synthetic') is False and critical.get('estimated') is False),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
