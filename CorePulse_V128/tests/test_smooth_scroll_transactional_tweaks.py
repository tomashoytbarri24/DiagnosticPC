"""Regresión V100: scroll estable + Tweaks transaccionales persistentes."""
from __future__ import annotations
from pathlib import Path
import getpass
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
    scroll = (ROOT/'gui'/'stable_scroll.py').read_text(encoding='utf-8')
    panel = (ROOT/'gui'/'windows_tweaks_panel.py').read_text(encoding='utf-8')
    engine = (ROOT/'core'/'windows_tweaks.py').read_text(encoding='utf-8')

    checks = [
        check('version', VERSION == '103'),
        check('stage', STAGE == 'EXE_RUNTIME_INTEGRITY'),
        check('scrollbar_drag_is_direct', 'self.canvas.yview_moveto' in scroll and '_target_offset' not in scroll),
        check('scroll_has_repaint_barrier', 'self.canvas.update_idletasks()' in scroll and 'RedrawWindow' in scroll),
        check('wheel_has_no_ghosting_interpolation', 'math.exp(' not in scroll and '_pending_wheel_px' not in scroll),
        check('tweaks_rows_are_native_and_light', 'Fila 100% Tk' in panel and 'tk.Frame(' in panel and "text='☐'" in panel),
        check('catalog_is_built_complete_not_progressively', 'for category, rows in self._catalog_groups:' in panel and 'self.frame.after_idle(self._build_catalog_step)' in panel),
        check('no_recursive_hover_tree', 'def bind_tree(' not in panel),
        check('rollback_ids_loaded_once_per_refresh', 'rollback_ids = saved_rollback_ids()' in panel),
        check('failure_names_are_visible', "failures.append(f'• {title}: {reason}')" in panel and "text='ERROR'" in panel),
        check('persistent_localappdata', "Path(local) / 'CorePulse' / 'state'" in engine),
        check('legacy_rollback_migration', '_migrate_legacy_storage_once' in engine and 'LEGACY_STATE_PATH' in engine),
        check('failed_apply_rolls_back', '_attempt_apply_rollback' in engine and 'Cambios parciales revertidos automáticamente.' in engine),
        check('failed_undo_keeps_rollback', 'El rollback permanece guardado para reintentar.' in engine),
        check('undo_is_verified_before_deleting_state', '_verify_undo_complete' in engine and "latest.get('tweaks', {}).pop(tweak_id, None)" in engine),
    ]

    # Prueba funcional del registro usando una tienda en memoria. No requiere Windows.
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
        'detect_tweak': wt.detect_tweak,
    }
    try:
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            wt.PERSISTENT_DATA_DIR = tdir
            wt.STATE_PATH = tdir/'windows_tweaks_state.json'
            wt.HISTORY_PATH = tdir/'windows_tweaks_history.jsonl'
            wt._MIGRATION_DONE = True
            wt.is_windows_11 = lambda: True
            wt.is_admin = lambda: True

            store = {}
            key = ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'HideFileExt')
            store[key] = (1, 4)

            def fake_read(hive, path, name):
                row = store.get((hive, path, name))
                return (True, row[0], row[1]) if row is not None else (False, None, None)

            def fake_write(hive, path, name, value, kind):
                store[(hive, path, name)] = (value, 4 if kind == 'dword' else 1)

            def fake_raw(hive, path, name, value, reg_type):
                store[(hive, path, name)] = (value, reg_type)

            def fake_delete(hive, path, name):
                store.pop((hive, path, name), None)

            wt._read_value = fake_read
            wt._write_value = fake_write
            wt._write_raw_value = fake_raw
            wt._delete_value = fake_delete

            applied = wt.apply_tweak('show_file_extensions')
            checks.append(check('functional_apply_verified', applied.get('success') and applied.get('verified') and store[key][0] == 0))
            checks.append(check('functional_rollback_persisted', 'show_file_extensions' in wt.saved_rollback_ids()))

            undone = wt.undo_tweak('show_file_extensions')
            checks.append(check('functional_undo_exact', undone.get('success') and undone.get('verified') and store[key] == (1, 4)))
            checks.append(check('functional_rollback_removed_only_after_success', 'show_file_extensions' not in wt.saved_rollback_ids()))

            # Fuerza fallo de verificación tras escribir: debe volver al original automáticamente.
            real_detect = wt.detect_tweak
            wt.detect_tweak = lambda _tid: {'id': _tid, 'status': 'not_applied', 'applied': False, 'detail': 'simulado'}
            store[key] = (1, 4)
            failed = wt.apply_tweak('show_file_extensions')
            checks.append(check('functional_failed_apply_auto_restores', (not failed.get('success')) and failed.get('rolled_back') and store[key] == (1, 4)))
            checks.append(check('functional_clean_failed_apply_has_no_orphan_rollback', 'show_file_extensions' not in wt.saved_rollback_ids()))
            wt.detect_tweak = real_detect
    finally:
        for name, value in originals.items():
            setattr(wt, name, value)

    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
