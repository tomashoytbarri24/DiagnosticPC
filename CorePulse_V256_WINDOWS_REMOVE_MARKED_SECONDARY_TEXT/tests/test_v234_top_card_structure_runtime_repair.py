from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_v234_version_contract():
    from core import version
    assert version.VERSION == '234'
    assert 'TOP_CARD_STRUCTURE_RUNTIME_REPAIR' in version.STAGE


def test_v234_startup_functions_exist():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    tree = ast.parse(text)
    defs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    required = {'_rebuild_sidebar','_rebuild_main_layout','_style_existing_cards','_style_charts','_wrap_telemetry_update','_wrap_disk_update','apply_professional_dashboard'}
    assert required <= defs


def test_v234_top_card_visual_structure():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert '_corepulse_resource_eyebrow' in text
    assert '_corepulse_storage_eyebrow' in text
    assert "title.pack_configure(fill='x', padx=(16, 14), pady=(29, 0))" in text
    assert "header.pack_configure(fill='x', padx=(16, 14), pady=(27, 3))" in text
    assert "_safe_config(self.lbl_cpu_title, text=str(cpu_name))" in text
    assert "_safe_config(self.lbl_ram_title, text='Uso físico del sistema')" in text
    assert "_safe_config(self.lbl_gpu_title, text=str(gpu_name))" in text


def test_v234_sidebar_lines_preserved():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'def _set_sidebar_option_line' in text
