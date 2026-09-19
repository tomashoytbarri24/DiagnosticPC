"""V100 — catálogo de optimización ampliado, reversible y consciente de edición."""
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
    items = wt.catalog()
    by = {x['id']: x for x in items}
    new_ids = {
        'disable_taskbar_window_sharing',
        'disable_account_notifications_start',
        'disable_clipboard_history',
        'disable_cross_device_clipboard',
        'disable_recent_documents_tracking',
        'disable_search_location',
        'disable_gamebar_controller_launch',
        'disable_game_dvr_policy',
        'disable_edge_startup_boost',
        'disable_edge_background_mode',
        'disable_windows_background_apps',
        'disable_search_highlights',
    }
    perf = set(wt.preset_ids('performance'))
    gaming = set(wt.preset_ids('gaming'))
    privacy = set(wt.preset_ids('privacy'))
    engine = (ROOT/'core'/'windows_tweaks.py').read_text(encoding='utf-8').lower()
    panel = (ROOT/'gui'/'windows_tweaks_panel.py').read_text(encoding='utf-8')

    checks = [
        check('version', VERSION.isdecimal()),
        check('stage', bool(STAGE)),
        check('catalog_expanded_to_78_plus', len(items) >= 78),
        check('new_tweaks_present', new_ids <= set(by)),
        check('dedicated_performance_category', 'Rendimiento' in {x['category'] for x in items}),
        check('edge_background_in_performance_preset', {'disable_edge_startup_boost','disable_edge_background_mode'} <= perf),
        check('controller_gamebar_in_gaming_preset', 'disable_gamebar_controller_launch' in gaming),
        check('recent_docs_is_privacy_opt_in', 'disable_recent_documents_tracking' in privacy),
        check('aggressive_background_apps_not_in_presets', 'disable_windows_background_apps' not in set().union(*(set(wt.preset_ids(k)) for k in wt.PRESETS))),
        check('edition_scoped_tweaks_declared', all(by[i].get('edition_scope') == 'pro_plus' for i in {
            'disable_clipboard_history','disable_cross_device_clipboard','disable_search_location',
            'disable_game_dvr_policy','disable_windows_background_apps','disable_search_highlights'})),
        check('edge_official_policy_values', by['disable_edge_startup_boost']['ops'][0][2:] == ('StartupBoostEnabled',0,'dword') and by['disable_edge_background_mode']['ops'][0][2:] == ('BackgroundModeEnabled',0,'dword')),
        check('gamebar_controller_official_user_value', by['disable_gamebar_controller_launch']['ops'][0][2:] == ('UseNexusForGameBarEnabled',0,'dword')),
        check('ui_exposes_windows_edition', "env.get('edition')" in panel),
        check('edition_availability_engine', '_availability(tweak)' in engine and 'edition_scope' in engine),
        check('no_hpet_nagle_timer_magic', not any(term in engine for term in ('useplatformclock', 'tcpackfrequency', 'networkthrottlingindex', 'disabledynamictick'))),
    ]

    originals = {
        'is_windows_11': wt.is_windows_11,
        'is_admin': wt.is_admin,
        '_windows_edition_id': wt._windows_edition_id,
        '_read_value': wt._read_value,
        '_write_value': wt._write_value,
        '_write_raw_value': wt._write_raw_value,
        '_delete_value': wt._delete_value,
        'STATE_PATH': wt.STATE_PATH,
        'HISTORY_PATH': wt.HISTORY_PATH,
        'PERSISTENT_DATA_DIR': wt.PERSISTENT_DATA_DIR,
        '_MIGRATION_DONE': wt._MIGRATION_DONE,
    }
    try:
        wt.is_windows_11 = lambda: True
        wt.is_admin = lambda: True
        wt._windows_edition_id = lambda: 'Core'
        home = wt.detect_tweak('disable_windows_background_apps')
        checks.append(check('home_gets_na_not_fake_applied', home.get('status') == 'unavailable' and 'Pro/Enterprise/Education' in home.get('detail','')))

        wt._windows_edition_id = lambda: 'Professional'
        wt._read_value = lambda *args: (False, None, None)
        pro = wt.detect_tweak('disable_windows_background_apps')
        checks.append(check('pro_can_expose_supported_tweak', pro.get('status') == 'not_applied'))

        # Verifica aplicación + rollback exacto de una optimización nueva de Edge.
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            wt.PERSISTENT_DATA_DIR = tdir
            wt.STATE_PATH = tdir/'windows_tweaks_state.json'
            wt.HISTORY_PATH = tdir/'windows_tweaks_history.jsonl'
            wt._MIGRATION_DONE = True
            store = {('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'StartupBoostEnabled'): (1, 4)}

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
            applied = wt.apply_tweak('disable_edge_startup_boost')
            checks.append(check('new_tweak_apply_verified', applied.get('success') and applied.get('verified') and store[('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'StartupBoostEnabled')][0] == 0))
            checks.append(check('new_tweak_rollback_saved', 'disable_edge_startup_boost' in wt.saved_rollback_ids()))
            undone = wt.undo_tweak('disable_edge_startup_boost')
            checks.append(check('new_tweak_undo_exact_anytime', undone.get('success') and store[('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'StartupBoostEnabled')] == (1, 4)))
            checks.append(check('rollback_removed_after_verified_undo', 'disable_edge_startup_boost' not in wt.saved_rollback_ids()))
    finally:
        for name, value in originals.items():
            setattr(wt, name, value)

    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
