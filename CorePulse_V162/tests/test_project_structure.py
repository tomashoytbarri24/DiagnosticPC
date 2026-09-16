"""Valida que el paquete final sea limpio, estable y libre de residuos de parches."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = []


def check(name, condition, detail=''):
    ok = bool(condition)
    RESULTS.append(ok)
    suffix = f' - {detail}' if detail else ''
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{suffix}")


def python_files():
    return sorted(path for path in ROOT.rglob('*.py') if '__pycache__' not in path.parts)


def unresolved_internal_imports():
    missing = []
    for path in python_files():
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and node.module.startswith(('core.', 'gui.', 'database.')):
                target = ROOT.joinpath(*node.module.split('.'))
                if not target.with_suffix('.py').exists() and not (target / '__init__.py').exists():
                    missing.append(f'{path.relative_to(ROOT)} -> {node.module}')
    return missing

files = [path for path in ROOT.rglob('*') if path.is_file()]
residue = [str(path.relative_to(ROOT)) for path in files if re.search(r'(^|/)(apply_ui|payload_ui|README_UI)|diagnose_relevance_v\d|test_.*ui\d+', str(path.relative_to(ROOT)), re.I)]
check('sin_residuos_de_parches', not residue, ', '.join(residue[:6]))
check('sin_git_privado', not (ROOT / '.git').exists())
check('sin_env_privado', not (ROOT / '.env').exists())
check('plantilla_env_segura', (ROOT / '.env.example').exists())
gitignore = (ROOT / '.gitignore').read_text(encoding='utf-8', errors='ignore') if (ROOT / '.gitignore').exists() else ''
check('cache_python_excluida_del_paquete', '__pycache__/' in gitignore and '*.py[cod]' in gitignore)
check('sin_modulos_pdf_legacy', not (ROOT / 'core' / 'report_layout.py').exists() and not (ROOT / 'core' / 'report_compact.py').exists())
check('constructor_pdf_renombrado', (ROOT / 'core' / 'report_builder.py').exists())
check('sin_ventana_secundaria_obsoleta', not (ROOT / 'gui' / 'secondary_window.py').exists())
check('arquitectura_documentada', (ROOT / 'ARQUITECTURA.md').exists())
check('presentmon_presente', (ROOT / 'tools' / 'presentmon' / 'PresentMon.exe').exists())

missing = unresolved_internal_imports()
check('imports_internos_resueltos', not missing, '; '.join(missing[:5]))

duplicates = []
for path in python_files():
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    names = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names[node.name] = names.get(node.name, 0) + 1
    duplicates.extend(f'{path.relative_to(ROOT)}:{name} x{count}' for name, count in names.items() if count > 1)
check('sin_definiciones_duplicadas', not duplicates, '; '.join(duplicates[:5]))

secret_pattern = re.compile(r'gsk_[A-Za-z0-9_-]{12,}')
secrets = []
for path in files:
    if path.suffix.lower() not in {'.py', '.md', '.txt', '.example', '.bat'} and path.name != '.env.example':
        continue
    try:
        if secret_pattern.search(path.read_text(encoding='utf-8', errors='ignore')):
            secrets.append(str(path.relative_to(ROOT)))
    except Exception:
        pass
check('sin_claves_groq_incrustadas', not secrets, ', '.join(secrets))

runtime_text = '\n'.join(path.read_text(encoding='utf-8', errors='ignore').lower() for path in [ROOT/'main.py', *sorted((ROOT/'core').glob('*.py')), *sorted((ROOT/'gui').glob('*.py'))])
test_machine_tokens = ('ge66', '10750h', 'rtx 2070', 'mzvlb512', 'pm981')
check('sin_hardware_de_prueba_hardcodeado', not any(token in runtime_text for token in test_machine_tokens))

parsed = True
errors = []
for path in python_files():
    try:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except SyntaxError as exc:
        parsed = False
        errors.append(f'{path.relative_to(ROOT)}:{exc.lineno}')
check('python_sintacticamente_valido', parsed, ', '.join(errors[:5]))

print('\nRESULTADO:', 'PASS' if all(RESULTS) else 'FAIL')
raise SystemExit(0 if all(RESULTS) else 1)
