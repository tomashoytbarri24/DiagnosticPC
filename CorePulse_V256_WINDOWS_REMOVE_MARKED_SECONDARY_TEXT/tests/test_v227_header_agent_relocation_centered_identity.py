from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def _func_source(path: Path, name: str) -> str:
    src = path.read_text(encoding='utf-8')
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node) or ''
    raise AssertionError(f'function {name} not found')


def test_v227_version_contract():
    from core import version
    assert version.VERSION == '227'
    assert 'HEADER_AGENT_RELOCATION_CENTERED_IDENTITY' in version.STAGE


def test_v227_header_owns_real_agent_and_centered_identity():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    header = _func_source(ROOT / 'gui' / 'dashboard.py', '_build_header')
    assert "identity.pack(expand=True)" in header
    assert "image=getattr(app, '_dashboard_brand_image', None)" in header
    assert "app._header_device_model" in header
    assert "text='ESTADO DEL AGENTE'" in header
    assert "app._agent_card = agent" in header
    assert "app._agent_status = status" in header
    assert "app._agent_state = state_label" in header
    assert "Monitoreo activo\\nAgente en ejecución" not in header
    assert "personalization_block.pack(side='top'" in dashboard


def test_v227_layout_no_longer_builds_agent_in_sidebar():
    layout_path = ROOT / 'gui' / 'dashboard_layout.py'
    build_agent = _func_source(layout_path, '_build_agent_card')
    assert "ctk.CTkFrame(app.sidebar" not in build_agent
    assert "_header_agent_frame" in build_agent
    sidebar_mode = _func_source(layout_path, '_style_sidebar_mode')
    assert "V227: no existe tarjeta de agente en el sidebar" in sidebar_mode


def test_v227_runtime_nameerror_regression_guards():
    layout_path = ROOT / 'gui' / 'dashboard_layout.py'
    sidebar_src = _func_source(layout_path, '_style_sidebar')
    header_src = _func_source(layout_path, '_style_header_mode')
    # Bugs observados en V223-V225: PRIMARY y compact fuera de su scope.
    assert 'PRIMARY' not in header_src
    assert not any(
        isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id == 'compact'
        for n in ast.walk(ast.parse(sidebar_src))
    )
