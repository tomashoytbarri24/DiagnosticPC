"""V100 — CorePulse debe cambiar, verificar y conservar el plan REAL de Windows."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from core.windows_commands import CommandResult
import performance.power_manager as pm
from performance.profile_manager import PerformanceProfileManager

CREATED_ULTIMATE = '11111111-2222-3333-4444-555555555555'


class Runner:
    def __init__(self):
        self.calls = []
        self.active = pm.BALANCED_GUID
        self.schemes = {
            pm.BALANCED_GUID: 'Equilibrado',
            pm.HIGH_PERFORMANCE_GUID: 'Alto rendimiento',
            pm.POWER_SAVER_GUID: 'Economizador',
        }

    def result(self, args, ok=True, out='', err='', rc=0):
        return CommandResult(ok, tuple(args), rc if ok else (rc or 1), out, err)

    def __call__(self, args, **kwargs):
        args = tuple(str(x) for x in args)
        self.calls.append(args)
        low = tuple(a.lower() for a in args)
        if '/getactivescheme' in low:
            name = self.schemes.get(self.active, 'Plan')
            return self.result(args, out=f'Power Scheme GUID: {self.active}  ({name})')
        if '/list' in low:
            lines = []
            for guid, name in self.schemes.items():
                star = ' *' if guid == self.active else ''
                lines.append(f'Power Scheme GUID: {guid}  ({name}){star}')
            return self.result(args, out='\n'.join(lines))
        if '/duplicatescheme' in low:
            template = low[-1]
            if template == pm.ULTIMATE_PERFORMANCE_GUID:
                self.schemes[CREATED_ULTIMATE] = 'Ultimate Performance'
                return self.result(args, out=f'Power Scheme GUID: {CREATED_ULTIMATE}')
            return self.result(args, ok=False, err='template unavailable', rc=1)
        if '/changename' in low:
            guid = low[2]
            self.schemes[guid] = args[3]
            return self.result(args)
        if '/delete' in low:
            guid = low[-1]
            self.schemes.pop(guid, None)
            return self.result(args)
        if '/setactive' in low:
            guid = low[-1]
            if guid not in self.schemes:
                return self.result(args, ok=False, err='missing plan', rc=1)
            self.active = guid
            return self.result(args)
        if '/qh' in low or '/query' in low:
            out = (
                f'Power Setting GUID: {pm.MAX_PROCESSOR_STATE}\nCurrent AC: 0x00000064\nCurrent DC: 0x00000064\n'
                f'Power Setting GUID: {pm.BOOST_MODE}\nCurrent AC: 0x00000001\nCurrent DC: 0x00000001\n'
                f'Power Setting GUID: {pm.PERF_EPP}\nCurrent AC: 0x00000032\nCurrent DC: 0x00000032\n'
            )
            return self.result(args, out=out)
        if '/setacvalueindex' in low or '/setdcvalueindex' in low:
            return self.result(args)
        return self.result(args)


class Detector:
    def detect_active_games(self):
        return []


class Boost:
    def set_notifier(self, cb): pass
    def status(self): return {'session_active': False, 'settings': {}}
    def get_settings(self): return {}
    def set_option(self, k, v): return True
    def sync_games(self, games, **kwargs): return {'success': True}
    def begin_session(self, games, **kwargs): return {'success': True}
    def end_session(self): return {'success': True}


def check(name, cond):
    ok = bool(cond)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    with tempfile.TemporaryDirectory() as td:
        backup = Path(td) / 'power_backup.json'
        old = pm.os.name
        pm.os.name = 'nt'
        try:
            runner = Runner()
            power = pm.PowerManager(runner=runner)
            results = [check('version', VERSION.isdecimal())]

            mgr = PerformanceProfileManager(
                power, Detector(), backup_path=backup,
                start_thread=False, register_atexit=False, game_boost=Boost(),
            )

            r = mgr.set_mode('HIGH_PERFORMANCE')
            results += [
                check('high_success', r.get('success')),
                check('high_changes_windows_active_plan', runner.active == pm.HIGH_PERFORMANCE_GUID),
                check('high_verified', r.get('windows_plan_verified')),
                check('status_reports_high', mgr.status().get('windows_plan_mode') == 'HIGH_PERFORMANCE'),
                check('status_in_sync', mgr.status().get('windows_plan_in_sync')),
            ]

            r = mgr.set_mode('POWER_SAVER')
            results += [
                check('saver_success', r.get('success')),
                check('saver_changes_windows_active_plan', runner.active == pm.POWER_SAVER_GUID),
            ]

            r = mgr.set_mode('MAXIMUM_PERFORMANCE')
            results += [
                check('ultimate_created_if_missing', r.get('success') and CREATED_ULTIMATE in runner.schemes),
                check('ultimate_is_active_in_windows', runner.active == CREATED_ULTIMATE),
                check('ultimate_named_corepulse', runner.schemes.get(CREATED_ULTIMATE) == 'CorePulse - Máximo rendimiento'),
            ]

            closed = mgr.shutdown()
            results += [
                check('shutdown_success', closed.get('success')),
                check('selected_windows_plan_persists_after_shutdown', runner.active == CREATED_ULTIMATE),
                check('created_ultimate_persists_after_shutdown', CREATED_ULTIMATE in runner.schemes),
                check('manual_transaction_has_no_pending_rollback', not backup.exists()),
            ]

            # Una nueva instancia debe leer el plan que Windows conserva, no
            # imponer Equilibrado ni depender de memoria de la sesión anterior.
            mgr2 = PerformanceProfileManager(
                power, Detector(), backup_path=backup,
                start_thread=False, register_atexit=False, game_boost=Boost(),
            )
            results += [
                check('restart_detects_persistent_maximum', mgr2.status().get('requested_mode') == 'MAXIMUM_PERFORMANCE'),
                check('restart_does_not_change_windows_plan', runner.active == CREATED_ULTIMATE),
            ]
            runner.active = pm.BALANCED_GUID
            mgr2.poll_games_once()
            results += [
                check('external_windows_change_is_respected', runner.active == pm.BALANCED_GUID),
                check('external_windows_change_updates_corepulse_state', mgr2.status().get('requested_mode') == 'BALANCED'),
            ]
            mgr2.shutdown()

            calls = [' '.join(c).lower() for c in runner.calls]
            results += [
                check('uses_powercfg_setactive', any('/setactive' in c for c in calls)),
                check('verifies_with_getactivescheme', sum('/getactivescheme' in c for c in calls) >= 3),
                check('uses_guid_not_localized_name', any(pm.HIGH_PERFORMANCE_GUID in c and '/setactive' in c for c in calls)),
            ]

            ok = all(results)
            print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
            return 0 if ok else 1
        finally:
            pm.os.name = old


if __name__ == '__main__':
    raise SystemExit(main())
