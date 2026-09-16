"""V100 — cuatro modos visibles y mapeados a planes reales de Windows."""
from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import VERSION
import performance.power_manager as pm
from performance.profile_manager import VISIBLE_MODES

def check(name,cond):
    ok=bool(cond); print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}"); return ok

def main():
    results=[
        check('version',VERSION == '103'),
        check('exact_four_visible_modes',VISIBLE_MODES==('BALANCED','HIGH_PERFORMANCE','MAXIMUM_PERFORMANCE','POWER_SAVER')),
        check('balanced_guid',pm.WINDOWS_MODE_SCHEMES['BALANCED']==pm.BALANCED_GUID),
        check('high_guid',pm.WINDOWS_MODE_SCHEMES['HIGH_PERFORMANCE']==pm.HIGH_PERFORMANCE_GUID),
        check('maximum_guid',pm.WINDOWS_MODE_SCHEMES['MAXIMUM_PERFORMANCE']==pm.ULTIMATE_PERFORMANCE_GUID),
        check('saver_guid',pm.WINDOWS_MODE_SCHEMES['POWER_SAVER']==pm.POWER_SAVER_GUID),
    ]
    ui=(ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    manager=(ROOT/'performance'/'profile_manager.py').read_text(encoding='utf-8')
    results += [
        check('ui_has_balanced',"('BALANCED', 'Equilibrado'" in ui),
        check('ui_has_high',"('HIGH_PERFORMANCE', 'Alto rendimiento'" in ui),
        check('ui_has_maximum',"('MAXIMUM_PERFORMANCE', 'Máximo rendimiento'" in ui),
        check('ui_has_saver',"('POWER_SAVER', 'Ahorro de energía'" in ui),
        check('ui_shows_windows_plan',"'PLAN DE WINDOWS'" in ui),
        check('ui_explains_windows_sync','Opciones de energía de Windows' in ui),
        check('manager_resolves_windows_scheme','ensure_mode_scheme' in manager),
        check('manager_saves_target_snapshot','scheme_snapshots' in manager),
    ]
    ok=all(results); print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}"); return 0 if ok else 1

if __name__=='__main__': raise SystemExit(main())
