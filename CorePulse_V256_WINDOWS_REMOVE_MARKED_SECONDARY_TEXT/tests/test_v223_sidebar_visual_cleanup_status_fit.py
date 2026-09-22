from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v223_version_contract():
    from core import version
    assert version.VERSION == '223'
    assert 'SIDEBAR_VISUAL_CLEANUP_STATUS_FIT' in version.STAGE


def test_v223_sidebar_rebuild_destroys_transient_widgets():
    src = (ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    assert 'if child in persistent:' in src
    assert 'child.destroy()' in src
    assert "'_personalization_block'" in src
    assert "setattr(app, attr, None)" in src


def test_v223_edge_preview_is_single_capsule_cascade():
    src = (ROOT/'main.py').read_text(encoding='utf-8')
    assert "'shadow_far': shadow_far" in src
    assert "'shadow_near': shadow_near" in src
    assert "'capsule': capsule" in src
    assert "(40, widgets['capsule']" in src
    assert "if x <= 104:" in src
    assert "if x <= 44:" in src


def test_v223_summary_text_is_concise_and_wrapped():
    live = (ROOT/'gui'/'live_health_binding.py').read_text(encoding='utf-8')
    dash = (ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    assert "title = 'Temperatura alta'" in live
    assert "detail = reason or 'Advertencia instantánea.'" in live
    assert "text=f'Índice {score_text} · estado unificado'" in live
    assert "text='Métricas certificadas'" in dash
    assert "wraplength=145 if compact else 172 if standard else 195" in layout
