"""Regresión: Windows Game Mode debe recuperar rollback tras cierre no limpio."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import performance.game_boost as gb


class _Key:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False


class FakeWinreg(types.SimpleNamespace):
    HKEY_CURRENT_USER = object()
    KEY_QUERY_VALUE = 1
    KEY_SET_VALUE = 2
    REG_DWORD = 4

    def __init__(self):
        super().__init__()
        self.values = {}

    def CreateKeyEx(self, *args, **kwargs):
        return _Key()

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name]

    def SetValueEx(self, key, name, reserved, reg_type, value):
        self.values[name] = (value, reg_type)

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    fake = FakeWinreg()
    old_windows = gb.IS_WINDOWS
    old_winreg = sys.modules.get('winreg')
    gb.IS_WINDOWS = True
    sys.modules['winreg'] = fake
    results = []
    try:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            config = base / 'settings.json'
            runtime = base / 'runtime.json'

            # Caso 1: valor previo 0 -> CorePulse pone 1 -> crash -> siguiente inicio restaura 0.
            fake.values['AutoGameModeEnabled'] = (0, fake.REG_DWORD)
            opt = gb.GameBoostOptimizer(config_path=config, runtime_backup_path=runtime)
            applied = opt._enable_windows_game_mode()
            results += [
                check('game_mode_applied', applied.get('success') and fake.values['AutoGameModeEnabled'][0] == 1),
                check('runtime_backup_persisted', runtime.is_file()),
                check('runtime_backup_reported_pending', opt.status().get('runtime_backup_pending') is True),
            ]
            # Simular cierre brusco: no llamar restore/end_session.
            recovered = gb.GameBoostOptimizer(config_path=config, runtime_backup_path=runtime)
            results += [
                check('startup_recovers_original_value', fake.values['AutoGameModeEnabled'][0] == 0),
                check('startup_clears_backup', not runtime.exists()),
                check('startup_reports_recovery', (recovered.status().get('recovery_status') or {}).get('restored') is True),
            ]

            # Caso 2: el valor no existía -> tras crash debe volver a no existir.
            fake.values.pop('AutoGameModeEnabled', None)
            opt2 = gb.GameBoostOptimizer(config_path=config, runtime_backup_path=runtime)
            applied2 = opt2._enable_windows_game_mode()
            check2a = applied2.get('success') and 'AutoGameModeEnabled' in fake.values
            recovered2 = gb.GameBoostOptimizer(config_path=config, runtime_backup_path=runtime)
            results += [
                check('missing_value_can_be_temporarily_created', check2a),
                check('startup_restores_missing_value', 'AutoGameModeEnabled' not in fake.values),
                check('missing_value_backup_cleared', not runtime.exists()),
            ]

            # Caso 3: cambio externo después del crash -> CorePulse no lo pisa.
            fake.values['AutoGameModeEnabled'] = (0, fake.REG_DWORD)
            opt3 = gb.GameBoostOptimizer(config_path=config, runtime_backup_path=runtime)
            applied3 = opt3._enable_windows_game_mode()
            fake.values['AutoGameModeEnabled'] = (0, fake.REG_DWORD)  # usuario/Windows lo cambia fuera de CorePulse
            recovered3 = gb.GameBoostOptimizer(config_path=config, runtime_backup_path=runtime)
            recovery3 = recovered3.status().get('recovery_status') or {}
            results += [
                check('external_change_setup', applied3.get('success')),
                check('external_change_not_overwritten', fake.values['AutoGameModeEnabled'][0] == 0),
                check('external_change_marks_skip', recovery3.get('skipped') is True),
                check('stale_backup_removed_after_safe_skip', not runtime.exists()),
            ]

            # Caso 4: cierre normal restaura y limpia backup.
            fake.values['AutoGameModeEnabled'] = (0, fake.REG_DWORD)
            opt4 = gb.GameBoostOptimizer(config_path=config, runtime_backup_path=runtime)
            applied4 = opt4._enable_windows_game_mode()
            restored4 = opt4._restore_windows_game_mode()
            results += [
                check('normal_restore_success', applied4.get('success') and restored4),
                check('normal_restore_original_value', fake.values['AutoGameModeEnabled'][0] == 0),
                check('normal_restore_clears_backup', not runtime.exists()),
            ]
    finally:
        gb.IS_WINDOWS = old_windows
        if old_winreg is None:
            sys.modules.pop('winreg', None)
        else:
            sys.modules['winreg'] = old_winreg

    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
