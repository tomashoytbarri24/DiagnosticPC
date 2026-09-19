from pathlib import Path
import ast
import tomllib

from core.version import STAGE, VERSION, VERSION_LABEL

ROOT = Path(__file__).resolve().parents[1]


def test_version_authority_is_synchronized():
    assert VERSION.isdecimal()
    assert STAGE
    assert (ROOT / 'LATEST_VERSION.txt').read_text(encoding='utf-8').strip() == VERSION_LABEL
    assert (ROOT / 'README.md').read_text(encoding='utf-8-sig').splitlines()[0] == f'# CorePulse {VERSION_LABEL}'
    assert (ROOT / 'VERSIONING.md').read_text(encoding='utf-8-sig').splitlines()[0] == f'# Versión actual: {VERSION_LABEL}'


def test_packaging_reads_version_from_core_authority():
    pyproject = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    assert 'version' in pyproject['project']['dynamic']
    assert 'version' not in pyproject['project']
    assert pyproject['tool']['setuptools']['dynamic']['version']['attr'] == 'core.version.VERSION'
    assert 'if not defined APPVER set' not in (ROOT / 'build_exe.bat').read_text(encoding='utf-8')
    assert 'if not defined APPVER set' not in (ROOT / 'build_installer.bat').read_text(encoding='utf-8')
    installer = (ROOT / 'installer/CorePulse.iss').read_text(encoding='utf-8')
    assert '#error MyAppVersion requerida' in installer


def test_test_modules_are_import_safe():
    offenders = []
    for path in sorted((ROOT / 'tests').glob('test_*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        if any(isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)
               and getattr(node.exc.func, 'id', '') == 'SystemExit' for node in tree.body):
            offenders.append(path.name)
    assert not offenders, offenders


def test_quality_gate_entrypoints_exist():
    assert (ROOT / 'quality_gate.py').is_file()
    assert (ROOT / 'Validar_CorePulse.bat').is_file()
    assert (ROOT / 'QUALITY_GATE.md').is_file()
