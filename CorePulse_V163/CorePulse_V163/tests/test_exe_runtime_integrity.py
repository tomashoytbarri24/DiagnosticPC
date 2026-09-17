"""Pruebas estáticas de la arquitectura EXE V0.10.2.55w."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, value):
    if not value:
        raise AssertionError(name)
    print("[PASS]", name)


def main():
    spec=(ROOT/'build/CorePulse.spec').read_text(encoding='utf-8')
    launcher=(ROOT/'corepulse_launcher.py').read_text(encoding='utf-8')
    tweaks=(ROOT/'core/windows_tweaks.py').read_text(encoding='utf-8')
    build=(ROOT/'build_exe.bat').read_text(encoding='utf-8')
    paths=(ROOT/'core/runtime_paths.py').read_text(encoding='utf-8')
    network=(ROOT/'gui/network_detail_panel.py').read_text(encoding='utf-8')

    check('version', VERSION == '103')
    check('stage', STAGE == 'STARTUP_RESPONSIVENESS_SINGLE_LAYOUT_AUTHORITY')
    check('hardwaremonitor_collected', 'collect_all(package)' in spec and '"HardwareMonitor"' in spec)
    check('speedtest_installer_bundled', 'Instalar_Speedtest_Ookla.bat' in spec)
    check('presentmon_bundled', '(str(ROOT / "tools"), "tools")' in spec)
    check('runtime_hook', 'corepulse_frozen_runtime.py' in spec)
    check('selftest_gate', '--corepulse-self-test' in build and 'FAIL_SELFTEST' in build)
    check('selftest_inside_launcher', '--corepulse-self-test' in launcher)
    check('same_exe_tweak_apply', '--corepulse-tweak-apply' in launcher and "_elevated_helper_target('apply'" in tweaks)
    check('same_exe_tweak_rollback', '--corepulse-tweak-rollback' in launcher and "_elevated_helper_target('rollback'" in tweaks)
    check('no_physical_helper_dependency', "with_name('tweak_apply_helper.py')" not in tweaks and "with_name('tweak_rollback_helper.py')" not in tweaks)
    check('appdata_authority', 'state_dir()' in paths and 'resource_root()' in paths)
    check('network_uses_resource_path', "resource_path('Instalar_Speedtest_Ookla.bat')" in network)
    check('mutable_data_not_in_spec', 'ROOT / "data"' not in spec and 'ROOT / "logs"' not in spec)

    # No módulo de producción debe crear su estado mutable relativo a __file__/data.
    offenders=[]
    for folder in ('core','gui','performance','database'):
        for p in (ROOT/folder).rglob('*.py'):
            text=p.read_text(encoding='utf-8', errors='ignore')
            if re.search(r"Path\(__file__\).*?['\"]data['\"]", text):
                # windows_tweaks mantiene sólo referencias LEGACY de migración.
                if p.name != 'windows_tweaks.py': offenders.append(str(p.relative_to(ROOT)))
    check('no_new_mutable_bundle_paths', not offenders)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
