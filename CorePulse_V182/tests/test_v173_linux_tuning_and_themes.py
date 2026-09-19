from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def test_linux_tuning_is_safe_and_platform_native():
    import core.linux_tuning as lt
    with patch.object(lt.platform, 'system', return_value='Linux'), patch.object(lt.shutil, 'which', return_value=None):
        info = lt.collect_linux_tuning()
    assert info['supported'] is True
    assert info['powerprofilesctl'] is False
    source = (ROOT / 'core' / 'linux_tuning.py').read_text(encoding='utf-8')
    assert "[tool, 'set', profile]" in source
    assert "subprocess.run(['sysctl'" not in source
    assert "powerprofilesctl" in source


def test_linux_navigation_uses_linux_adjustments_not_windows_tweaks():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "'Ajustes Linux'" in main
    assert 'open_platform_tweaks' in main
    assert "'Tweaks Windows 11' if platform.system() == 'Windows' else 'Ajustes Linux'" in dashboard


def test_linux_window_removes_right_bottom_gutters():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert "if IS_LINUX:" in main
    assert "padx=(15, 0), pady=(15, 0)" in main


def test_theme_gallery_has_filters_palette_and_preview():
    panel = (ROOT / 'gui' / 'theme_panel.py').read_text(encoding='utf-8')
    assert "('Todos', 'Oscuros', 'Claros')" in panel
    assert "text='PALETA'" in panel
    assert 'self.preview_swatches' in panel
    assert "text='Vista previa'" in panel
