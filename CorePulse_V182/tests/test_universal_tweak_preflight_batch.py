"""V100 — preflight universal, N/A real y aplicación UAC particionada."""
from __future__ import annotations
from pathlib import Path
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
    checks = [check('version', VERSION.isdecimal())]
    panel = (ROOT/'gui'/'windows_tweaks_panel.py').read_text(encoding='utf-8')
    helper = (ROOT/'core'/'tweak_apply_helper.py').read_text(encoding='utf-8')
    engine = (ROOT/'core'/'windows_tweaks.py').read_text(encoding='utf-8')
    checks += [
        check('select_all_compatible_label', 'Seleccionar todos los tweaks' in panel),
        check('ui_distinguishes_na', "f'{unavailable} no disponibles'" in panel and "text='NO DISPONIBLE'" in panel),
        check('apply_auto_uac_copy', 'Windows mostrará UAC sólo para los tweaks que realmente requieren administrador' in panel),
        check('helper_receives_persisted_snapshots', 'apply_snapshot_records(records)' in helper),
        check('helper_not_state_owner', 'saved_rollback_ids' not in helper and '_save_state' not in helper),
        check('engine_partitions_apply_batch', 'user_ids =' in engine and 'admin_ids =' in engine and '_apply_many_elevated(admin_ids)' in engine),
    ]

    originals = {
        'is_windows_11': wt.is_windows_11,
        '_windows_edition_id': wt._windows_edition_id,
        'platform_system': wt.platform.system,
        'is_admin': wt.is_admin,
        'apply_tweak': wt.apply_tweak,
        '_apply_many_elevated': wt._apply_many_elevated,
    }
    try:
        wt.is_windows_11 = lambda: True
        wt._windows_edition_id = lambda: 'Core'
        compatible = set(wt.compatible_tweak_ids())
        checks.append(check('home_keeps_generic_tweak', 'show_file_extensions' in compatible))
        checks.append(check('home_excludes_pro_policy', 'disable_clipboard_history' not in compatible))
        pf = wt.preflight_tweak('disable_clipboard_history')
        checks.append(check('pro_only_is_na_not_error', (not pf.get('applicable')) and pf.get('status') == 'unavailable'))

        # Un lote mixto debe mantener HKCU en el usuario y elevar sólo el admin.
        wt.platform.system = lambda: 'Windows'
        wt.is_admin = lambda: False
        direct, elevated = [], []
        def fake_apply(tid):
            direct.append(tid)
            return {'success': True, 'id': tid, 'status': 'applied'}
        def fake_elevated(ids):
            elevated.extend(ids)
            return [{'success': True, 'id': x, 'status': 'applied'} for x in ids]
        wt.apply_tweak = fake_apply
        wt._apply_many_elevated = fake_elevated
        rows = wt.apply_many(['show_file_extensions', 'disable_lock_screen'], auto_elevate=True)
        checks.append(check('hkcu_apply_stays_user', direct == ['show_file_extensions']))
        checks.append(check('only_admin_apply_elevated', elevated == ['disable_lock_screen']))
        checks.append(check('apply_order_preserved', [x.get('id') for x in rows] == ['show_file_extensions', 'disable_lock_screen']))
    finally:
        wt.is_windows_11 = originals['is_windows_11']
        wt._windows_edition_id = originals['_windows_edition_id']
        wt.platform.system = originals['platform_system']
        wt.is_admin = originals['is_admin']
        wt.apply_tweak = originals['apply_tweak']
        wt._apply_many_elevated = originals['_apply_many_elevated']

    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
