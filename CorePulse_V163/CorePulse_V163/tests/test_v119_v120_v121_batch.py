"""Regresión V121 — V119 recuperación + V120 salud inteligente + V121 Startup Analyzer."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.session_recovery import SessionRecoveryManager
from core.health_intelligence import build_health_intelligence
import core.startup_analyzer as sa


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    results = []
    results += [
        check('version_121', VERSION == '121'),
        check('stage_batch', STAGE == 'CRASH_RECOVERY_HEALTH_INTELLIGENCE_STARTUP_ANALYZER'),
    ]

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        session = base / 'active.json'
        history = base / 'history.json'
        session.write_text(json.dumps({
            'active': True, 'clean_shutdown': False, 'version': 'V120',
            'pid': 999999, 'process_create_time': 1.0,
            'started_at': '2026-09-14T00:00:00+00:00',
            'last_heartbeat_at': '2026-09-14T00:01:00+00:00',
        }), encoding='utf-8')
        mgr = SessionRecoveryManager(session_path=session, history_path=history, crash_dir=base / 'crash_reports')
        status = mgr.begin_session()
        results += [
            check('unclean_session_detected', isinstance(status.get('previous_abnormal'), dict)),
            check('new_session_marker_written', session.is_file()),
            check('crash_report_created', bool(status.get('crash_report_path')) and Path(status['crash_report_path']).is_file()),
        ]
        mgr.record_recovery_action('Game Boost', True, 'Rollback temporal restaurado')
        results.append(check('recovery_action_recorded', mgr.status()['recovery_actions'][0]['success'] is True))
        mgr.mark_clean_shutdown()
        results += [
            check('clean_shutdown_removes_marker', not session.exists()),
            check('recovery_history_persisted', any(x.get('type') == 'abnormal_shutdown' for x in mgr.history(10))),
        ]

    normal = build_health_intelligence(
        {'cpu_temp': 55, 'gpu_temp': 62}, [], preliminary_score=92,
        battery={'present': True, 'health_percent': 91}, throttling={'cpu': {'state': 'NO_EVIDENCE'}},
    )
    critical = build_health_intelligence({'cpu_temp': 98, 'gpu_temp': 60}, [], preliminary_score=90)
    battery_warning = build_health_intelligence(
        {'cpu_temp': 50}, [], preliminary_score=90, battery={'present': True, 'health_percent': 55}
    )
    missing = build_health_intelligence({}, [{'name': 'SSD', 'health': None}], preliminary_score=None)
    crash_warning = build_health_intelligence(
        {'cpu_temp': 50}, [], preliminary_score=90,
        crashes={'counts': {'bsod_bugcheck': 1, 'whea': 0, 'kernel_power': 0, 'unexpected_shutdown': 0}}
    )
    results += [
        check('health_normal_real_data', normal['state'] == 'NORMAL' and normal['synthetic'] is False),
        check('health_critical_temperature', critical['state'] == 'CRITICAL'),
        check('health_battery_warning', battery_warning['state'] == 'WARNING'),
        check('health_na_not_penalized', missing['state'] == 'NO_EVALUABLE'),
        check('health_windows_crash_attention', crash_warning['state'] == 'WARNING'),
        check('health_policy_no_synthetic', 'NO_SYNTHETIC_SCORE' in normal['policy']),
    ]

    # En Linux debe degradar sin intentar escribir Registro. En Windows devuelve inventario real.
    startup = sa.collect_startup_items()
    results += [
        check('startup_contract', isinstance(startup.get('items'), list) and 'policy' in startup),
        check('startup_disable_requires_explicit_source', sa.disable_startup_item('missing')['success'] is False),
    ]

    main_text = (ROOT / 'main.py').read_text(encoding='utf-8')
    panel_text = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    startup_text = (ROOT / 'core' / 'startup_analyzer.py').read_text(encoding='utf-8')
    results += [
        check('main_marks_session', 'SessionRecoveryManager' in main_text and 'mark_clean_shutdown' in main_text),
        check('recovery_after_rollbacks', main_text.index('mark_clean_shutdown') > main_text.index('finalize_persistent_plan')),
        check('health_summary_visible', 'EVALUACIÓN GENERAL' in panel_text and 'build_health_intelligence' in panel_text),
        check('startup_ui_actions', 'Deshabilitar' in panel_text and 'Restaurar' in panel_text and '_startup_action' in panel_text),
        check('startup_system_guard', "scope != 'HKCU'" in startup_text and 'USER_REVERSIBLE_ONLY' in startup_text),
        check('startup_external_change_guard', 'No se sobrescribirá un cambio externo' in startup_text),
    ]

    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
