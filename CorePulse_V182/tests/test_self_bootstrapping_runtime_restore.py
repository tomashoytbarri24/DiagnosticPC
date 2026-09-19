"""V100 — runtime fuente autocurable entre PCs Windows."""
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, value):
    if not value:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    bootstrap = (ROOT/'bootstrap_corepulse.py').read_text(encoding='utf-8')
    source_bootstrap = (ROOT/'core/source_runtime_bootstrap.py').read_text(encoding='utf-8')
    vbs = (ROOT/'CorePulse.vbs').read_text(encoding='utf-8')
    helper = (ROOT/'CorePulse_Bootstrap.bat').read_text(encoding='utf-8')
    launcher = (ROOT/'corepulse_launcher.py').read_text(encoding='utf-8')
    main_py = (ROOT/'main.py').read_text(encoding='utf-8')
    runtime_lock = (ROOT/'requirements-runtime-lock.txt').read_text(encoding='utf-8')

    check('version', VERSION.isdecimal())
    check('runtime_lock_exists', (ROOT/'requirements-runtime-lock.txt').is_file())
    check('matplotlib_bundled_policy', 'matplotlib==3.11.1' in runtime_lock)
    check('platformdirs_bundled_policy', 'platformdirs==4.11.7' in runtime_lock)
    check('hardwaremonitor_runtime', 'HardwareMonitor==1.2.1' in runtime_lock and 'pythonnet==3.1.0' in runtime_lock)
    check('source_bootstrap_stdlib_first', 'ensure_source_runtime()' in launcher and launcher.index('ensure_source_runtime()') < launcher.index('from core.runtime_paths'))
    check('main_self_heals', 'from core.source_runtime_bootstrap import ensure_source_runtime' in main_py and 'ensure_source_runtime()' in main_py[:500])
    check('vbs_no_manual_install_requirement', 'instalar_dependencias.bat' not in vbs and 'CorePulse_Bootstrap.bat' in vbs)
    check('helper_supports_existing_venv', '.venv\\Scripts\\python.exe' in helper)
    check('helper_finds_python312', 'py -3.12' in helper)
    check('bootstrap_creates_venv', '"-m", "venv"' in bootstrap)
    check('bootstrap_installs_runtime_lock', 'requirements-runtime-lock.txt' in bootstrap and '"pip", "install"' in bootstrap)
    check('bootstrap_validates_matplotlib', 'matplotlib' in bootstrap and '_verify_imports' in bootstrap)
    check('bootstrap_validates_lhm', 'LibreHardwareMonitorLib.dll' in bootstrap and 'HidSharp.dll' in bootstrap)
    check('bootstrap_relaunches_local_pythonw', 'VENV_PYW' in bootstrap and 'corepulse_launcher.py' in bootstrap)
    check('marker_not_only_authority', '_marker_valid(lock_hash)' in bootstrap and '_verify_imports()' in bootstrap)

    check('pythonw_is_local_runtime', '_venv_pythonw(root)' in source_bootstrap and '_same_executable(current, local_pythonw)' in source_bootstrap)

    # Importar el guard en CI/Linux no debe disparar procesos ni exigir Windows.
    spec = importlib.util.spec_from_file_location('cp_source_bootstrap_test', ROOT/'core/source_runtime_bootstrap.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ensure_source_runtime()
    check('ci_non_windows_noop', True)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
