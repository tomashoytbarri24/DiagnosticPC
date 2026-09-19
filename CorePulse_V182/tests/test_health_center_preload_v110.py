"""V110 — batería predecidida y Centro de Salud sin consultas redundantes."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import VERSION, STAGE
from core.battery_health import probe_battery_presence

def check(name, cond):
    if not cond: raise AssertionError(name)
    print('[PASS]', name)

def main():
    main_py=(ROOT/'main.py').read_text(encoding='utf-8')
    panel=(ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    batt=(ROOT/'core'/'battery_health.py').read_text(encoding='utf-8')
    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('fast_presence_api', 'GetSystemPowerStatus' in batt and 'def probe_battery_presence' in batt)
    check('presence_primed_before_health_center', 'self._prime_battery_presence_cache()' in main_py)
    check('health_center_uses_presence_seed', 'self._seed_preloaded_battery_state()' in panel)
    check('battery_full_refresh_global_cache', 'apply_battery_health_cache' in panel and '_schedule_battery_health_refresh' in main_py)
    check('summary_does_not_load_hw_compare', "if key == 'history' and self._hw is None" in panel)
    check('hardware_compare_cached', 'health_center_hardware_cache_timestamp' in panel)
    check('health_center_prewarmed', '_prewarm_health_center_module' in main_py)
    check('powercfg_is_fallback', 'need_report = any(' in batt)
    print('RESULTADO: PASS')

if __name__=='__main__': main()
