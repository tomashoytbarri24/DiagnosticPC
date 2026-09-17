"""V100 — rollback redundante, reintentos, UAC y selección total."""
from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core import windows_tweaks as wt


def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {bool(cond)}")
    return bool(cond)


def main():
    panel = (ROOT/'gui'/'windows_tweaks_panel.py').read_text(encoding='utf-8')
    engine = (ROOT/'core'/'windows_tweaks.py').read_text(encoding='utf-8')
    helper = (ROOT/'core'/'tweak_rollback_helper.py').read_text(encoding='utf-8')
    checks = [
        check('version', VERSION == '103'),
        check('stage', STAGE == 'STARTUP_RESPONSIVENESS_SINGLE_LAYOUT_AUTHORITY'),
        check('select_all_button', "text='Seleccionar todos los tweaks'" in panel and 'def _select_all' in panel),
        check('undo_all_action', 'Deshacer TODO lo aplicado' in panel and 'def _run_undo_all' in panel),
        check('undo_all_uses_persistent_snapshots', 'undo_all_saved(auto_elevate=True)' in panel),
        check('normal_undo_filters_to_snapshots', "if action == 'undo':" in panel and 'rollback_ids = saved_rollback_ids()' in panel),
        check('apply_admin_partition', "Windows mostrará UAC sólo para los tweaks que realmente requieren administrador" in panel and 'auto_elevate=True' in panel),
        check('undo_mentions_uac', 'Windows mostrará UAC' in panel),
        check('redundant_state_copy', "windows_tweaks_state.backup.json" in engine and "'revision'" in engine),
        check('newest_state_wins', 'max(valid, key=_state_rank)' in engine),
        check('undo_retries', 'for attempt in range(1, max_attempts + 1)' in engine and 'time.sleep(0.18 * attempt)' in engine),
        check('verified_before_snapshot_delete', "state.get('tweaks', {}).pop(tweak_id, None)" in engine and '_verify_undo_complete' in engine),
        check('auto_elevation_engine', 'def _undo_many_elevated' in engine and "-Verb RunAs -Wait -PassThru" in engine),
        check('elevated_helper_only_undoes', 'wt.restore_snapshot_records(records, attempts=3)' in helper and 'apply_tweak' not in helper),
    ]

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
        '_undo_many_elevated': wt._undo_many_elevated,
        'platform_system': wt.platform.system,
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

            store = {
                ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'HideFileExt'): (1, 4),
                ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'LaunchTo'): (2, 4),
            }
            raw_failures = {'left': 0}

            def fake_read(hive, path, name):
                row = store.get((hive, path, name))
                return (True, row[0], row[1]) if row is not None else (False, None, None)

            def fake_write(hive, path, name, value, kind):
                store[(hive, path, name)] = (value, 4 if kind == 'dword' else 1)

            def fake_raw(hive, path, name, value, reg_type):
                if raw_failures['left'] > 0:
                    raw_failures['left'] -= 1
                    raise OSError('bloqueo transitorio simulado')
                store[(hive, path, name)] = (value, reg_type)

            def fake_delete(hive, path, name):
                store.pop((hive, path, name), None)

            wt._read_value = fake_read
            wt._write_value = fake_write
            wt._write_raw_value = fake_raw
            wt._delete_value = fake_delete

            a = wt.apply_tweak('show_file_extensions')
            b = wt.apply_tweak('open_this_pc')
            checks.append(check('two_tweaks_applied', a.get('success') and b.get('success')))
            backup = wt.STATE_PATH.with_name('windows_tweaks_state.backup.json')
            checks.append(check('primary_and_backup_exist', wt.STATE_PATH.is_file() and backup.is_file()))
            checks.append(check('two_rollbacks_saved', {'show_file_extensions','open_this_pc'} <= wt.saved_rollback_ids()))

            # Corrompe el principal: el espejo debe rescatar la reversión.
            wt.STATE_PATH.write_text('{broken json', encoding='utf-8')
            recovered = wt.saved_rollback_ids()
            checks.append(check('backup_recovers_corrupt_primary', {'show_file_extensions','open_this_pc'} <= recovered))
            checks.append(check('primary_auto_repaired', wt.STATE_PATH.read_text(encoding='utf-8').lstrip().startswith('{')))

            # Un fallo transitorio al restaurar debe reintentarse y terminar bien.
            raw_failures['left'] = 1
            undone = wt.undo_tweak('show_file_extensions', attempts=3)
            key1 = ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'HideFileExt')
            checks.append(check('retry_eventually_restores', undone.get('success') and undone.get('attempts') == 2 and store[key1] == (1, 4)))
            checks.append(check('snapshot_deleted_only_after_verified_retry', 'show_file_extensions' not in wt.saved_rollback_ids()))

            all_results = wt.undo_all_saved(auto_elevate=False)
            key2 = ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'LaunchTo')
            checks.append(check('undo_all_saved_restores_remaining', len(all_results) == 1 and all_results[0].get('success') and store[key2] == (2, 4)))
            checks.append(check('no_rollbacks_left_after_verified_undo_all', not wt.saved_rollback_ids()))

            # El batch debe delegar en elevación si cualquier rollback lo requiere.
            wt.platform.system = lambda: 'Windows'
            wt.is_admin = lambda: False
            called = {}
            def fake_elevated(ids):
                called['ids'] = list(ids)
                return [{'success': True, 'id': x, 'verified': True} for x in ids]
            wt._undo_many_elevated = fake_elevated
            elevated = wt.undo_many(['disable_edge_startup_boost'], auto_elevate=True)
            checks.append(check('non_admin_undo_auto_elevates', called.get('ids') == ['disable_edge_startup_boost'] and elevated[0].get('success')))
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
        wt._undo_many_elevated = originals['_undo_many_elevated']
        wt.platform.system = originals['platform_system']

    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
