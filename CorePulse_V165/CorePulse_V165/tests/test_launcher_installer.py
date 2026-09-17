"""Regresión del launcher fuente y flujo de distribución V100."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import VERSION, STAGE

def check(name, cond):
    if not cond: raise AssertionError(name)
    print('[PASS]',name)

def main():
    vbs=(ROOT/'CorePulse.vbs').read_text(encoding='utf-8',errors='replace')
    launch=(ROOT/'Iniciar_CorePulse.bat').read_text(encoding='utf-8',errors='replace')
    deps=(ROOT/'instalar_dependencias.bat').read_text(encoding='utf-8',errors='replace')
    build=(ROOT/'build_exe.bat').read_text(encoding='utf-8',errors='replace')
    installer=(ROOT/'build_installer.bat').read_text(encoding='utf-8',errors='replace')
    check('version', VERSION == '113')
    check('stage', STAGE == 'BENCHMARK_PRECONFIGURATION_FLOW')
    check('source_vbs_direct_launcher', 'corepulse_launcher.py' in vbs and 'CorePulse_Bootstrap.bat' not in vbs)
    check('compat_launcher_uses_vbs', 'CorePulse.vbs' in launch and 'wscript.exe' in launch)
    check('deps_requires_source_root', 'main.py' in deps and 'corepulse_launcher.py' in deps)
    check('deps_uses_python_312_release', 'py -3.12' in deps and 'requirements-win-lock.txt' in deps)
    check('deps_verifies_hardwaremonitor', 'LibreHardwareMonitorLib.dll' in deps and 'HardwareMonitor.Hardware import Computer' in deps)
    check('build_runs_exe_selftest', '--corepulse-self-test' in build and 'CorePulse_EXE_SELFTEST.json' in build)
    check('installer_requires_selftest', 'CorePulse_EXE_SELFTEST.json' in installer)
    print('RESULTADO: PASS')
if __name__=='__main__': main()
