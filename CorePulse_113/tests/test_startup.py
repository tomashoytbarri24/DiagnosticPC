"""Prueba de humo para detectar errores de importación y problemas de arranque."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
from pathlib import Path
import ast
import builtins
import importlib
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.version import VERSION_LABEL
checks = []

def check(name, cond):
    checks.append(bool(cond))
    print(f"[{('PASS' if cond else 'FAIL')}] {name}: {bool(cond)}")
try:
    dialogs = importlib.import_module('gui.dialogs')
    check('dialogs_imports_cleanly', True)
    check('dialogs_version_defined', str(getattr(dialogs, 'VERSION', '')) == VERSION_LABEL)
except Exception as exc:
    print(f'[DETAIL] dialogs import failed: {type(exc).__name__}: {exc}')
    check('dialogs_imports_cleanly', False)
    check('dialogs_version_defined', False)

try:
    contract = importlib.import_module('core.product_contract')
    integration = importlib.import_module('gui.integration')
    check('product_contract_stage_exported', bool(getattr(contract, 'STAGE', '')))
    check('runtime_integration_imports_cleanly', callable(getattr(integration, 'apply_runtime_integration', None)))
except Exception as exc:
    print(f'[DETAIL] runtime integration import failed: {type(exc).__name__}: {exc}')
    check('product_contract_stage_exported', False)
    check('runtime_integration_imports_cleanly', False)

violations = []
for path in list((ROOT / 'gui').glob('*.py')) + list((ROOT / 'core').glob('*.py')):
    text = path.read_text(encoding='utf-8')
    if 'VERSION_LABEL' not in text:
        continue
    if path.name == 'version.py':
        continue
    tree = ast.parse(text)
    imports_version = False
    imports_contract = False
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            imported_names = {alias.name for alias in node.names}
            if node.module == 'core.version' and 'VERSION_LABEL' in imported_names:
                imports_version = True
            if node.module == 'core.product_contract' and 'VERSION_LABEL' in imported_names:
                imports_contract = True
    if not (imports_version or imports_contract):
        violations.append(str(path.relative_to(ROOT)))
check('version_label_has_authority_import', not violations)
if violations:
    print('[DETAIL] Missing VERSION_LABEL import:', violations)
runtime = [ROOT / 'main.py'] + list((ROOT / 'core').glob('*.py')) + list((ROOT / 'gui').glob('*.py')) + list((ROOT / 'database').glob('*.py'))
parse_ok = True
for path in runtime:
    try:
        ast.parse(path.read_text(encoding='utf-8'))
    except Exception as exc:
        print(f'[DETAIL] Parse failed {path.relative_to(ROOT)}: {exc}')
        parse_ok = False
check('all_runtime_python_parses', parse_ok)
print('\nRESULT:', 'PASS' if all(checks) else 'FAIL')
raise SystemExit(0 if all(checks) else 1)
