from pathlib import Path
import ast
import builtins
import symtable
import sys
import types

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


def test_v236_version_contract():
    from core import version
    assert version.VERSION == '236'
    assert 'RESOURCE_STATUS_CARD_RUNTIME_STABILITY' in version.STAGE


def test_v236_dashboard_has_no_undefined_runtime_globals():
    assert _undefined_global_refs(ROOT / 'gui' / 'dashboard.py') == set()


def test_v236_dashboard_layout_has_no_undefined_runtime_globals():
    assert _undefined_global_refs(ROOT / 'gui' / 'dashboard_layout.py') == set()


def test_v236_required_dashboard_functions_exist_via_import_smoke():
    old = sys.modules.get('customtkinter')
    sys.modules['customtkinter'] = types.ModuleType('customtkinter')
    try:
        sys.modules.pop('gui.dashboard', None)
        import gui.dashboard as dashboard
        for name in ('_rebuild_sidebar', '_rebuild_main_layout', '_style_existing_cards', '_ensure_resource_card_decor'):
            assert hasattr(dashboard, name), name
        assert dashboard.ICON_FONT == 'Segoe UI Symbol'
    finally:
        sys.modules.pop('gui.dashboard', None)
        if old is not None:
            sys.modules['customtkinter'] = old
        else:
            sys.modules.pop('customtkinter', None)
