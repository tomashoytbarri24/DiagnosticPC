from pathlib import Path
import ast
import builtins
import symtable

ROOT = Path(__file__).resolve().parents[1]


def _undefined_global_refs(path: Path):
    src = path.read_text(encoding='utf-8')
    tree = ast.parse(src)
    module_defs = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_defs.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module_defs.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                module_defs.add(alias.asname or alias.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    module_defs.add(target.id)
    known = module_defs | set(dir(builtins))
    root = symtable.symtable(src, str(path), 'exec')
    suspects = set()
    def walk(table):
        for symbol in table.get_symbols():
            if symbol.is_referenced() and symbol.is_global() and symbol.get_name() not in known:
                suspects.add(symbol.get_name())
        for child in table.get_children():
            walk(child)
    walk(root)
    return suspects


def test_v226_version_contract():
    from core import version
    assert version.VERSION == '226'
    assert 'SIDEBAR_RUNTIME_NAMEERROR_FIX' in version.STAGE


def test_v226_dashboard_layout_has_no_undefined_runtime_globals():
    suspects = _undefined_global_refs(ROOT / 'gui' / 'dashboard_layout.py')
    assert suspects == set(), suspects


def test_v226_specific_regressions_are_removed():
    src = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert "text_color=CYAN)" in src
    assert "text_color=PRIMARY)" not in src
    assert "font=(FONT, 11 if compact else 12, 'bold')" not in src
    assert "text_color=SIDEBAR_INACTIVE_TEXT, font=(FONT, 11, 'bold')" in src
