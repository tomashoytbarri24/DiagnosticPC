"""V100 — los planes manuales persisten; sólo Game Boost es temporal."""
from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from performance.profile_manager import PerformanceProfileManager


class Boost:
    def __init__(self):
        self.active = False
        self.end_calls = 0
    def set_notifier(self, cb): pass
    def status(self): return {'session_active': self.active, 'settings': {}, 'runtime_backup_pending': self.active}
    def get_settings(self): return {}
    def set_option(self, k, v): return True
    def sync_games(self, games, **kwargs): self.active = bool(games); return {'success': True}
    def begin_session(self, games, **kwargs): self.active = bool(games); return {'success': True}
    def end_session(self): self.end_calls += 1; self.active = False; return {'success': True}


class Detector:
    def detect_active_games(self): return []


class Power:
    def __init__(self, fail=False):
        self.fail = fail
        self.active_mode = 'BALANCED'
        self.active_guid = 'balanced-guid'
        self.restore_calls = 0
    def active_windows_plan(self):
        return {'success': True, 'guid': self.active_guid, 'name': self.active_mode, 'mode': self.active_mode}
    def snapshot(self):
        return {'success': True, 'original': {
            'active_scheme_guid': self.active_guid,
            'settings': {}, 'capabilities': {},
        }}
    def ensure_mode_scheme(self, mode):
        return {'success': True, 'mode': mode, 'guid': mode.lower() + '-guid', 'name': mode, 'created': False}
    def snapshot_scheme(self, scheme):
        return {'success': True, 'settings': {}, 'capabilities': {}}
    def _apply(self, profile, scheme):
        if self.fail:
            return {'success': False, 'message': 'fallo simulado'}
        self.active_mode = profile
        self.active_guid = scheme
        return {'success': True, 'profile': profile, 'windows_plan_guid': scheme, 'windows_plan_name': profile, 'windows_plan_verified': True, 'message': profile}
    def apply_balanced(self, scheme, settings=None): return self._apply('BALANCED', scheme)
    def apply_high_performance(self, scheme, settings=None): return self._apply('HIGH_PERFORMANCE', scheme)
    def apply_maximum_performance(self, scheme, settings=None): return self._apply('MAXIMUM_PERFORMANCE', scheme)
    def apply_power_saver(self, scheme, settings=None): return self._apply('POWER_SAVER', scheme)
    def restore(self, backup):
        self.restore_calls += 1
        original = (backup or {}).get('original') or {}
        self.active_guid = original.get('active_scheme_guid') or self.active_guid
        self.active_mode = 'BALANCED'
        return {'success': True, 'message': 'Restaurado'}
    def activate_balanced_default(self):
        self.active_mode = 'BALANCED'; self.active_guid = 'balanced-guid'
        return {'success': True}


def check(name, cond):
    ok = bool(cond)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    results = [check('version', VERSION == '103')]
    with tempfile.TemporaryDirectory() as td:
        backup = Path(td) / 'profile_tx.json'
        power = Power(); boost = Boost()
        mgr = PerformanceProfileManager(power, Detector(), backup_path=backup, start_thread=False, register_atexit=False, game_boost=boost)
        applied = mgr.set_mode('MAXIMUM_PERFORMANCE')
        results += [
            check('manual_apply_success', applied.get('success')),
            check('manual_result_is_persistent', applied.get('persistent') is True),
            check('no_pending_backup_after_commit', not backup.exists()),
            check('maximum_active_before_close', power.active_mode == 'MAXIMUM_PERFORMANCE'),
        ]
        closed = mgr.shutdown()
        results += [
            check('normal_shutdown_success', closed.get('success')),
            check('normal_shutdown_does_not_restore_plan', power.restore_calls == 0),
            check('maximum_still_active_after_close', power.active_mode == 'MAXIMUM_PERFORMANCE'),
            check('gameboost_still_stops', boost.end_calls >= 1),
        ]
        mgr2 = PerformanceProfileManager(power, Detector(), backup_path=backup, start_thread=False, register_atexit=False, game_boost=Boost())
        results += [
            check('restart_reads_windows_active_plan', mgr2.status().get('requested_mode') == 'MAXIMUM_PERFORMANCE'),
            check('restart_does_not_force_balanced', power.active_mode == 'MAXIMUM_PERFORMANCE'),
        ]
        mgr2.shutdown()

    with tempfile.TemporaryDirectory() as td:
        backup = Path(td) / 'failed_tx.json'
        power = Power(fail=True)
        mgr = PerformanceProfileManager(power, Detector(), backup_path=backup, start_thread=False, register_atexit=False, game_boost=Boost())
        failed = mgr.set_mode('HIGH_PERFORMANCE')
        results += [
            check('failed_apply_reports_failure', not failed.get('success')),
            check('failed_apply_rolls_back_immediately', power.restore_calls == 1),
            check('failed_transaction_cleared_after_rollback', not backup.exists()),
        ]

    manager_src = (ROOT/'performance'/'profile_manager.py').read_text(encoding='utf-8')
    health_src = (ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    safe_src = (ROOT/'core'/'safe_shutdown.py').read_text(encoding='utf-8')
    results += [
        check('atexit_preserves_manual_plan', 'self.shutdown(restore=False)' in manager_src),
        check('shutdown_default_is_persistent', 'def shutdown(self, restore: bool = False)' in manager_src),
        check('ui_explains_persistence', 'El plan queda activo aunque cierres CorePulse' in health_src),
        check('admin_restart_preserves_plan', 'manager.shutdown(restore=False)' in health_src),
        check('safe_shutdown_contract_updated', 'persistent Windows plan preserved' in safe_src),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
