from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def _load_compat():
    spec = importlib.util.spec_from_file_location('cp_python_compat', ROOT / 'core' / 'python_compat.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_policy_accepts_newer_minors():
    source = (ROOT / 'core' / 'python_compat.py').read_text(encoding='utf-8')
    assert 'version[:2] >= tuple(MIN_PYTHON)' in source
    assert 'no_artificial_upper_bound' in source


def test_installer_has_no_exact_312_gate():
    source = (ROOT / 'instalar_dependencias.bat').read_text(encoding='utf-8')
    assert 'sys.version_info[:2]>=(3,12)' in source
    assert 'sys.version_info[:2]==(3,12)' not in source
    assert 'py -3.12 -c' not in source
    assert 'requirements-runtime-flex.txt' in source
    assert 'validate_python_runtime.py' in source


def test_build_uses_validated_runtime_pointer():
    source = (ROOT / 'build_exe.bat').read_text(encoding='utf-8')
    assert '.corepulse_runtime_python.txt' in source
    assert 'sys.version_info[:2]>=(3,12)' in source
    assert 'sys.version_info[:2]==(3,12)' not in source


def test_entrypoints_bootstrap_runtime():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    launcher = (ROOT / 'corepulse_launcher.py').read_text(encoding='utf-8')
    assert 'bootstrap_validated_runtime(__file__)' in main
    assert 'bootstrap_validated_runtime(__file__)' in launcher
