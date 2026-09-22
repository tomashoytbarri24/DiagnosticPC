from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v217_version_contract():
    from core import version
    assert version.VERSION == "217"
    assert "CLASSIC_STARTUP_WINDOW_SIZE_FIX" in version.STAGE


def test_v217_classic_geometry_constants_and_preset():
    src = (ROOT / 'gui' / 'adaptive_window.py').read_text(encoding='utf-8')
    assert 'PREFERRED_W = 1280' in src
    assert 'PREFERRED_H = 800' in src
    assert "'Recomendado': (1280, 800)" in src
    assert "'Amplio': (1560, 860)" in src


def test_v217_automatic_does_not_scale_up_with_monitor():
    src = (ROOT / 'gui' / 'adaptive_window.py').read_text(encoding='utf-8')
    assert 'width = min(PREFERRED_W, max_w)' in src
    assert 'height = min(PREFERRED_H, max_h)' in src
    assert 'No expande CorePulse en pantallas grandes' in src
    assert 'width_ratio' not in src[src.index('def _automatic_size(app):'):src.index('def _fit_size(app, width, height):')]


def test_v217_migrates_old_recommended_size_but_preserves_custom():
    src = (ROOT / 'gui' / 'adaptive_window.py').read_text(encoding='utf-8')
    assert "if preset_name == 'Recomendado' and (rw > PREFERRED_W or rh > PREFERRED_H):" in src
    assert "elif preset_name == 'Automático':" in src
    assert 'Personalizado escogido por el usuario se conserva intacto' in src


def test_v217_startup_reasserts_geometry_after_deiconify():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'def _settle_startup_geometry():' in main
    assert "self.after(120, _settle_startup_geometry)" in main
    assert "apply_preferred_launch_geometry(self, force=True)" in main
