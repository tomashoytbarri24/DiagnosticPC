"""Regresión de V0.10.0.0w — biblioteca extendida de Tweaks Windows 11."""
from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core import windows_tweaks as wt


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    dashboard=(ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    main_text=(ROOT/'main.py').read_text(encoding='utf-8')
    nav=(ROOT/'gui'/'internal_navigation.py').read_text(encoding='utf-8')
    ui=(ROOT/'gui'/'ui_consistency.py').read_text(encoding='utf-8')
    panel=(ROOT/'gui'/'windows_tweaks_panel.py').read_text(encoding='utf-8')
    engine=(ROOT/'core'/'windows_tweaks.py').read_text(encoding='utf-8').lower()
    items=wt.catalog(); ids={x['id'] for x in items}
    high={x['id'] for x in items if x['risk'] in ('Alto','Crítico')}
    auto=set()
    for preset in ('minimal','recommended','privacy','gaming','performance','advanced'):
        auto.update(wt.preset_ids(preset))
    results=[
        check('version', VERSION=='0.10.0.0w'),
        check('stage', STAGE=='HEALTH_INTELLIGENCE_RECOVERY'),
        check('logo_only_sidebar', "_safe_pack_forget(app.lbl_brand)" in dashboard and "_safe_config(app.lbl_brand, text='')" in dashboard and "_safe_config(app.lbl_subtitle, text='')" in dashboard),
        check('tweaks_sidebar_button', 'btn_tweaks' in dashboard and 'Tweaks Windows 11' in dashboard),
        check('tweaks_navigation_registered', "'tweaks': 'btn_tweaks'" in nav and "'tweaks': 'windows_tweaks_panel'" in nav),
        check('tweaks_dispatcher_registered', "'btn_tweaks': ('tweaks'" in ui),
        check('main_opens_tweaks', 'def open_windows_tweaks' in main_text and 'WindowsTweaksPanel' in main_text),
        check('six_presets', {'minimal','recommended','privacy','gaming','performance','advanced'} <= set(wt.PRESETS)),
        check('extended_catalog_size', len(ids) >= 60),
        check('many_categories', len({x['category'] for x in items}) >= 10),
        check('reversible_state', 'windows_tweaks_state.json' in engine and 'undo_tweak' in engine and 'originals' in engine),
        check('no_remote_script_execution', 'christitus.com/win' not in engine and 'invoke-webrequest' not in engine and 'invoke-expression' not in engine),
        check('edge_remove_present', 'remove_edge' in ids and 'webview2' in engine),
        check('onedrive_remove_present', 'remove_onedrive' in ids),
        check('widgets_remove_present', 'remove_widgets_package' in ids),
        check('defender_advanced_present', 'disable_defender_stack' in ids),
        check('security_controls_present', {'disable_smartscreen','disable_uac','disable_memory_integrity','disable_vbs'} <= ids),
        check('windows_update_advanced_present', {'exclude_driver_updates','no_auto_reboot_updates','disable_auto_updates'} <= ids),
        check('high_risk_never_in_presets', high.isdisjoint(auto)),
        check('high_risk_double_confirmation', '_confirm_high_risk' in panel and 'CONFIRMACIÓN CRÍTICA' in panel),
        check('admin_gate', 'requires_admin' in panel and 'Administrador requerido' in panel),
        check('panel_has_apply_undo', 'Aplicar seleccionados' in panel and 'Deshacer seleccionados' in panel),
        check('panel_restore_point_optional', 'Crear punto de restauración' in panel),
        check('panel_explorer_restart_manual', 'Reiniciar Explorador' in panel),
        check('engine_imports_cross_platform', isinstance(wt.environment_info(), dict)),
    ]
    ok=all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
