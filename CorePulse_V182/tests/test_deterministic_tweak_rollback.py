"""V100 — rollback determinista, batch UAC separado y comandos exactos."""
from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from core import windows_tweaks as wt


def check(name, cond):
    ok = bool(cond)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    checks = []
    checks.append(check('version', VERSION.isdecimal()))

    panel = (ROOT/'gui'/'windows_tweaks_panel.py').read_text(encoding='utf-8')
    helper = (ROOT/'core'/'tweak_rollback_helper.py').read_text(encoding='utf-8')
    engine = (ROOT/'core'/'windows_tweaks.py').read_text(encoding='utf-8')
    checks.append(check('select_all_exact_label', "Seleccionar todos los tweaks" in panel))
    checks.append(check('ui_exposes_rollback_status', 'APLICADO · ROLLBACK ✓' in panel and 'PREEXISTENTE · SIN SNAPSHOT' in panel))
    checks.append(check('helper_receives_snapshots', 'restore_snapshot_records(records, attempts=3)' in helper and "payload.get('records')" in helper))
    checks.append(check('helper_does_not_load_parent_state', 'undo_many(' not in helper and 'saved_rollback_ids' not in helper))
    checks.append(check('mixed_batch_is_partitioned', 'user_ids =' in engine and 'admin_ids =' in engine and '_undo_many_elevated(admin_ids)' in engine))

    by = {x['id']: x for x in wt.TWEAKS}
    old_win11 = wt.is_windows_11
    try:
        wt.is_windows_11 = lambda: True
        guaranteed, _ = wt._rollback_guarantee(by['disable_hibernation'])
        blocked, reason = wt._rollback_guarantee(by['remove_edge'])
        checks.append(check('hibernation_has_exact_strategy', guaranteed and by['disable_hibernation']['undo_mode'] == 'exact'))
        checks.append(check('destructive_new_apply_blocked', (not blocked) and 'rollback' in reason.lower()))
    finally:
        wt.is_windows_11 = old_win11

    originals = {
        'STATE_PATH': wt.STATE_PATH,
        'HISTORY_PATH': wt.HISTORY_PATH,
        'PERSISTENT_DATA_DIR': wt.PERSISTENT_DATA_DIR,
        '_MIGRATION_DONE': wt._MIGRATION_DONE,
        'is_windows_11': wt.is_windows_11,
        'is_admin': wt.is_admin,
        '_read_value': wt._read_value,
        '_write_value': wt._write_value,
        '_write_raw_value': wt._write_raw_value,
        '_delete_value': wt._delete_value,
        '_run_powershell': wt._run_powershell,
        '_current_user_sid': wt._current_user_sid,
        'platform_system': wt.platform.system,
        'undo_tweak': wt.undo_tweak,
        '_undo_many_elevated': wt._undo_many_elevated,
    }
    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wt.PERSISTENT_DATA_DIR = root
            wt.STATE_PATH = root/'windows_tweaks_state.json'
            wt.HISTORY_PATH = root/'windows_tweaks_history.jsonl'
            wt._MIGRATION_DONE = True
            wt.is_windows_11 = lambda: True
            wt.is_admin = lambda: True
            wt._current_user_sid = lambda: 'S-1-5-21-COREPULSE-USER'

            store = {
                ('HKLM', r'SYSTEM\CurrentControlSet\Control\Session Manager\Power', 'HibernateEnabled'): (0, 4),
                ('HKLM', r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FlyoutMenuSettings', 'ShowHibernateOption'): (1, 4),
            }
            commands = []

            def fake_read(hive, path, name):
                row = store.get((hive, path, name))
                return (True, row[0], row[1]) if row is not None else (False, None, None)

            def fake_write(hive, path, name, value, kind):
                store[(hive, path, name)] = (value, 4 if kind == 'dword' else 1)

            def fake_raw(hive, path, name, value, reg_type):
                store[(hive, path, name)] = (value, reg_type)

            def fake_delete(hive, path, name):
                store.pop((hive, path, name), None)

            def fake_ps(script, timeout=45):
                commands.append(str(script))
                return {'success': True, 'returncode': 0, 'stdout': '', 'stderr': ''}

            wt._read_value = fake_read
            wt._write_value = fake_write
            wt._write_raw_value = fake_raw
            wt._delete_value = fake_delete
            wt._run_powershell = fake_ps

            applied = wt.apply_tweak('disable_hibernation')
            checks.append(check('apply_requires_persisted_snapshot', applied.get('success') and applied.get('rollback_available') and 'disable_hibernation' in wt.saved_rollback_ids()))
            state = wt._load_state()
            record = state['tweaks']['disable_hibernation']
            checks.append(check('snapshot_has_owner_sid', record.get('owner_sid') == 'S-1-5-21-COREPULSE-USER'))
            checks.append(check('snapshot_has_command_state', record.get('command_snapshot', {}).get('enabled') is False))

            commands.clear()
            undone = wt.undo_tweak('disable_hibernation')
            checks.append(check('undo_succeeds', undone.get('success') and undone.get('verified')))
            checks.append(check('hibernation_restores_original_off_not_default_on', any('/hibernate off' in cmd for cmd in commands) and not any('/hibernate on' in cmd for cmd in commands)))
            checks.append(check('registry_restored_exactly', store[('HKLM', r'SYSTEM\CurrentControlSet\Control\Session Manager\Power', 'HibernateEnabled')] == (0, 4) and store[('HKLM', r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FlyoutMenuSettings', 'ShowHibernateOption')] == (1, 4)))
            checks.append(check('snapshot_removed_only_after_success', 'disable_hibernation' not in wt.saved_rollback_ids()))

            # Caso raíz del bug: lote mixto no debe elevar un tweak HKCU.
            wt.platform.system = lambda: 'Windows'
            wt.is_admin = lambda: False
            direct_calls = []
            elevated_calls = []
            def fake_undo(tid, attempts=3):
                direct_calls.append(tid)
                return {'success': True, 'verified': True, 'id': tid}
            def fake_elevated(ids):
                elevated_calls.extend(ids)
                return [{'success': True, 'verified': True, 'id': x} for x in ids]
            wt.undo_tweak = fake_undo
            wt._undo_many_elevated = fake_elevated
            mixed = wt.undo_many(['show_file_extensions', 'disable_lock_screen'], auto_elevate=True)
            checks.append(check('hkcu_undo_stays_in_original_user', direct_calls == ['show_file_extensions']))
            checks.append(check('only_hklm_admin_tweak_is_elevated', elevated_calls == ['disable_lock_screen']))
            checks.append(check('mixed_result_order_preserved', [x.get('id') for x in mixed] == ['show_file_extensions', 'disable_lock_screen']))
    finally:
        wt.STATE_PATH = originals['STATE_PATH']
        wt.HISTORY_PATH = originals['HISTORY_PATH']
        wt.PERSISTENT_DATA_DIR = originals['PERSISTENT_DATA_DIR']
        wt._MIGRATION_DONE = originals['_MIGRATION_DONE']
        wt.is_windows_11 = originals['is_windows_11']
        wt.is_admin = originals['is_admin']
        wt._read_value = originals['_read_value']
        wt._write_value = originals['_write_value']
        wt._write_raw_value = originals['_write_raw_value']
        wt._delete_value = originals['_delete_value']
        wt._run_powershell = originals['_run_powershell']
        wt._current_user_sid = originals['_current_user_sid']
        wt.platform.system = originals['platform_system']
        wt.undo_tweak = originals['undo_tweak']
        wt._undo_many_elevated = originals['_undo_many_elevated']

    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
