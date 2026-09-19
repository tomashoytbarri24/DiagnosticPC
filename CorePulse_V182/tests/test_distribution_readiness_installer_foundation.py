"""Regresión de readiness/distribución evolucionada a V100."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import VERSION, STAGE
from core.startup_readiness import collect_readiness

def check(name, cond):
    if not cond: raise AssertionError(name)
    print('[PASS]',name)

def main():
    launcher=(ROOT/'corepulse_launcher.py').read_text(encoding='utf-8')
    spec=(ROOT/'build/CorePulse.spec').read_text(encoding='utf-8')
    iss=(ROOT/'installer/CorePulse.iss').read_text(encoding='utf-8')
    build=(ROOT/'build_exe.bat').read_text(encoding='utf-8')
    check('version',VERSION.isdecimal())
    check('stage',bool(STAGE))
    check('launcher_fast_gate_before_gui','collect_launch_gate' in launcher and 'from main import App' in launcher and launcher.index('collect_launch_gate(VERSION)') < launcher.index('from main import App'))
    check('full_readiness_deferred','_deferred_integrity_worker' in launcher and 'collect_readiness' in launcher and 'CorePulse-RuntimeIntegrity' in launcher)
    check('internal_modes_before_gui','_handle_internal_mode()' in launcher and '--corepulse-self-test' in launcher)
    check('pyinstaller_onedir','exclude_binaries=True' in spec and 'COLLECT(' in spec)
    check('hardwaremonitor_collection','collect_all(package)' in spec and 'HardwareMonitor' in spec)
    check('inno_per_user','DefaultDirName={localappdata}\\Programs\\CorePulse' in iss and 'PrivilegesRequired=lowest' in iss)
    check('build_selftest_gate','FAIL_SELFTEST' in build)
    report=collect_readiness(ROOT,VERSION)
    check('readiness_structured',bool(report.items) and isinstance(report.ready,bool))
    check('has_degradable_capabilities',any(not i.required for i in report.items))
    print('RESULTADO: PASS')
if __name__=='__main__': main()
