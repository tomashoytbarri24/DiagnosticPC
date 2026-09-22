from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v218_version_contract():
    from core import version
    assert version.VERSION == '218'
    assert 'STEAM_LIKE_STARTUP_WINDOW_SIZE' in version.STAGE


def test_v218_steam_like_geometry_contract():
    src = (ROOT / 'gui' / 'adaptive_window.py').read_text(encoding='utf-8')
    assert 'PREFERRED_W = 1280' in src
    assert 'PREFERRED_H = 720' in src
    assert "'Recomendado': (1280, 720)" in src
    assert "'Compacto': (1180, 680)" in src
    assert "'Amplio': (1560, 860)" in src
    assert 'width = min(PREFERRED_W, max_w)' in src
    assert 'height = min(PREFERRED_H, max_h)' in src


def test_v218_product_contract_matches_visible_presets():
    src = (ROOT / 'core' / 'product_contract.py').read_text(encoding='utf-8')
    assert "'Compacto': (1180, 680)" in src
    assert "'Recomendado': (1280, 720)" in src
    assert "'Amplio': (1560, 860)" in src


def test_v218_sidebar_does_not_resize_outer_window():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    start = main.index('def set_sidebar_collapsed')
    end = main.find('\n    def ', start + 10)
    block = main[start:end]
    assert '.geometry(' not in block
    assert '.state(' not in block
