"""V100 — Restore Center persistente y detección de cambios externos."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
import core.windows_tweaks as wt


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def test_inventory_states():
    original_load = wt._load_state
    original_owner = wt._state_owner_matches
    original_lookup = wt._tweak_by_id
    original_detect = wt.detect_tweak
    original_original_match = wt._rollback_original_matches
    original_details = wt.rollback_change_details
    original_events = wt._rollback_last_events
    try:
        state = {
            'user': 'tester',
            'tweaks': {
                'a': {'saved_at': 3, 'undo_mode': 'exact'},
                'b': {'saved_at': 2, 'undo_mode': 'exact'},
                'c': {'saved_at': 1, 'undo_mode': 'exact'},
            },
        }
        wt._load_state = lambda: state
        wt._state_owner_matches = lambda value: True
        wt._tweak_by_id = lambda tid: {
            'id': tid, 'title': f'Tweak {tid}', 'description': '', 'category': 'Prueba',
            'risk': 'Bajo', 'requires_admin': False, 'requires_restart': False,
            'requires_explorer': False, 'undo_mode': 'exact',
        }
        wt.detect_tweak = lambda tid: {
            'a': {'status': 'applied', 'applied': True},
            'b': {'status': 'not_applied', 'applied': False},
            'c': {'status': 'partial', 'applied': False},
        }[tid]
        wt._rollback_original_matches = lambda tweak, record: (
            tweak['id'] == 'b', [] if tweak['id'] == 'b' else ['different']
        )
        wt.rollback_change_details = lambda tid: [{'location': tid, 'before': '1', 'applied': '0'}]
        wt._rollback_last_events = lambda limit=1000: {}
        rows = wt.rollback_inventory()
        states = {row['id']: row['state'] for row in rows}
        return states == {
            'a': 'applied',
            'b': 'restored_externally',
            'c': 'modified_externally',
        }
    finally:
        wt._load_state = original_load
        wt._state_owner_matches = original_owner
        wt._tweak_by_id = original_lookup
        wt.detect_tweak = original_detect
        wt._rollback_original_matches = original_original_match
        wt.rollback_change_details = original_details
        wt._rollback_last_events = original_events


def test_history_reader():
    original_path = wt.HISTORY_PATH
    original_migration = wt._MIGRATION_DONE
    try:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'history.jsonl'
            tid = wt.TWEAKS[0]['id']
            rows = [
                {'timestamp': 1.0, 'tweak_id': tid, 'action': 'apply', 'success': True, 'message': 'ok'},
                {'timestamp': 2.0, 'tweak_id': tid, 'action': 'undo', 'success': True, 'message': 'restored'},
            ]
            path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n', encoding='utf-8')
            wt.HISTORY_PATH = path
            wt._MIGRATION_DONE = True
            history = wt.tweak_history(limit=10)
            return (
                len(history) == 2
                and history[0]['event_label'] == 'REVERTIDO'
                and history[1]['event_label'] == 'APLICADO'
            )
    finally:
        wt.HISTORY_PATH = original_path
        wt._MIGRATION_DONE = original_migration


def main():
    panel = (ROOT / 'gui' / 'windows_tweaks_panel.py').read_text(encoding='utf-8')
    center = (ROOT / 'gui' / 'tweak_restore_center.py').read_text(encoding='utf-8')
    engine = (ROOT / 'core' / 'windows_tweaks.py').read_text(encoding='utf-8')
    checks = [
        check('version', VERSION == '103'),
        check('restore_center_internal', 'TweakRestoreCenter' in panel and 'def _open_restore_center' in panel and 'pack(fill=\'both\', expand=True)' in panel),
        check('restore_center_button', "text='Centro de restauración'" in panel),
        check('active_and_history_views', "values=['Cambios activos', 'Historial']" in center),
        check('selection_based_restore', "text='Restaurar seleccionados'" in center and "text='Restaurar TODO'" in center),
        check('no_per_row_restore_button', center.count("text='Restaurar seleccionados'") == 1 and center.count("text='Restaurar TODO'") == 1),
        check('external_change_warning', 'CAMBIO EXTERNO DETECTADO' in center and 'modified_externally' in center),
        check('inventory_api', 'def rollback_inventory()' in engine and 'RESTAURADO EXTERNAMENTE' in engine and 'MODIFICADO EXTERNAMENTE' in engine),
        check('exact_value_details', 'def rollback_change_details' in engine and "'before':" in engine and "'applied':" in engine),
        check('persistent_history_api', 'def tweak_history(' in engine and 'HISTORY_PATH' in engine),
        check('inventory_state_machine', test_inventory_states()),
        check('history_order_and_labels', test_history_reader()),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
