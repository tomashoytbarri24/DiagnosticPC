"""V100 — el cierre no puede deshacer el plan manual persistente."""
from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from performance.profile_manager import PerformanceProfileManager


class Detector:
    def detect_active_games(self):
        return []


class Power:
    GUIDS = {
        'BALANCED': 'balanced-guid',
        'HIGH_PERFORMANCE': 'high-guid',
        'MAXIMUM_PERFORMANCE': 'maximum-guid',
        'POWER_SAVER': 'saver-guid',
    }

    def __init__(self):
        self.active_mode = 'HIGH_PERFORMANCE'
        self.active_guid = self.GUIDS[self.active_mode]
        self.set_active_calls = []
        self.restore_calls = 0

    def active_windows_plan(self):
        return {
            'success': True,
            'guid': self.active_guid,
            'name': self.active_mode,
            'mode': self.active_mode,
        }

    def snapshot(self):
        return {'success': True, 'original': {
            'active_scheme_guid': self.active_guid,
            'settings': {}, 'capabilities': {},
        }}

    def ensure_mode_scheme(self, mode):
        return {
            'success': True, 'mode': mode,
            'guid': self.GUIDS[mode], 'name': mode,
            'created': False,
        }

    def snapshot_scheme(self, scheme):
        return {'success': True, 'settings': {}, 'capabilities': {}}

    def _apply(self, mode, scheme):
        self.active_mode = mode
        self.active_guid = scheme
        return {
            'success': True, 'profile': mode,
            'windows_plan_guid': scheme,
            'windows_plan_name': mode,
            'windows_plan_verified': True,
            'message': mode,
        }

    def apply_balanced(self, scheme, settings=None): return self._apply('BALANCED', scheme)
    def apply_high_performance(self, scheme, settings=None): return self._apply('HIGH_PERFORMANCE', scheme)
    def apply_maximum_performance(self, scheme, settings=None): return self._apply('MAXIMUM_PERFORMANCE', scheme)
    def apply_power_saver(self, scheme, settings=None): return self._apply('POWER_SAVER', scheme)

    def set_active(self, scheme, verify=True):
        self.set_active_calls.append(str(scheme))
        reverse = {v: k for k, v in self.GUIDS.items()}
        if scheme not in reverse:
            return {'success': False, 'message': 'GUID desconocido'}
        self.active_guid = scheme
        self.active_mode = reverse[scheme]
        return {'success': True, 'guid': scheme, 'verified': bool(verify)}

    def restore(self, backup):
        self.restore_calls += 1
        guid = ((backup or {}).get('original') or {}).get('active_scheme_guid')
        if guid:
            self.set_active(guid)
        return {'success': True}

    def activate_balanced_default(self):
        return self.set_active(self.GUIDS['BALANCED'])


class BoostThatRevertsPower:
    """Simula el bug observado: un teardown temporal deja otro plan activo."""
    def __init__(self, power):
        self.power = power
        self.end_calls = 0
    def set_notifier(self, cb): pass
    def status(self): return {'session_active': True, 'settings': {}, 'runtime_backup_pending': True}
    def get_settings(self): return {}
    def set_option(self, k, v): return True
    def sync_games(self, games, **kwargs): return {'success': True}
    def begin_session(self, games, **kwargs): return {'success': True}
    def end_session(self):
        self.end_calls += 1
        # Reproduce exactamente la clase de regresión vista en Windows:
        # durante el cierre otra restauración temporal deja Alto rendimiento.
        self.power.active_mode = 'HIGH_PERFORMANCE'
        self.power.active_guid = self.power.GUIDS['HIGH_PERFORMANCE']
        return {'success': True, 'message': 'temporales restaurados'}


def check(name, cond):
    ok = bool(cond)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    results = [check('version', VERSION.isdecimal())]
    with tempfile.TemporaryDirectory() as td:
        backup = Path(td) / 'tx.json'
        power = Power()
        boost = BoostThatRevertsPower(power)
        mgr = PerformanceProfileManager(
            power, Detector(), backup_path=backup,
            start_thread=False, register_atexit=False, game_boost=boost,
        )
        results += [
            check('startup_reads_high_performance', mgr.status()['requested_mode'] == 'HIGH_PERFORMANCE'),
        ]
        applied = mgr.set_mode('MAXIMUM_PERFORMANCE')
        results += [
            check('maximum_applies', applied.get('success')),
            check('maximum_guid_active', power.active_guid == power.GUIDS['MAXIMUM_PERFORMANCE']),
            check('maximum_committed_exact_guid', mgr.status().get('committed_manual_guid') == power.GUIDS['MAXIMUM_PERFORMANCE']),
        ]
        closed = mgr.shutdown()
        results += [
            check('shutdown_success', closed.get('success')),
            check('boost_teardown_ran', boost.end_calls == 1),
            check('shutdown_reasserts_maximum_after_teardown', power.active_guid == power.GUIDS['MAXIMUM_PERFORMANCE']),
            check('shutdown_reasserts_mode_too', power.active_mode == 'MAXIMUM_PERFORMANCE'),
            check('no_rollback_to_original', power.restore_calls == 0),
            check('exact_guid_reasserted', power.GUIDS['MAXIMUM_PERFORMANCE'] in power.set_active_calls),
        ]

        # Una nueva instancia debe leer el plan REAL que sobrevivió al cierre.
        mgr2 = PerformanceProfileManager(
            power, Detector(), backup_path=backup,
            start_thread=False, register_atexit=False,
            game_boost=BoostThatRevertsPower(power),
        )
        results += [
            check('restart_reads_surviving_maximum_plan', mgr2.status()['requested_mode'] == 'MAXIMUM_PERFORMANCE'),
            check('restart_does_not_fallback_balanced', mgr2.status()['requested_mode'] != 'BALANCED'),
        ]
        # No llamamos shutdown del segundo manager porque su boost fake simula
        # deliberadamente una alteración; no hubo selección manual que reafirmar.

    manager_src = (ROOT/'performance'/'profile_manager.py').read_text(encoding='utf-8')
    safe_src = (ROOT/'core'/'safe_shutdown.py').read_text(encoding='utf-8')
    health_src = (ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    main_src = (ROOT/'main.py').read_text(encoding='utf-8')
    results += [
        check('shutdown_finalization_exists', 'def finalize_persistent_plan' in manager_src),
        check('shutdown_finalizes_after_gameboost', 'boost_result = self.game_boost.end_session()' in manager_src and 'persisted = self.finalize_persistent_plan()' in manager_src),
        check('safe_shutdown_final_verification', "performance plan: final Windows GUID verified" in safe_src),
        check('main_last_moment_power_guard', "self._shutdown_power_persistence_result = finalize()" in main_src and "inmediatamente antes de destruir la aplicación" in main_src),
        check('ui_no_fake_balanced_fallback', "status.get('requested_mode') or 'UNKNOWN'" in health_src),
    ]

    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
