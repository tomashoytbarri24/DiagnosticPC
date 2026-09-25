from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_only_platform_artifacts():
    retired = ROOT / 'core' / ('storage_health_' + 'lin' + 'ux.py')
    assert not retired.exists()
    assert 'platform = "Windows only"' in (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
    compat = (ROOT / 'core' / 'python_compat.py').read_text(encoding='utf-8')
    assert "os.name != 'nt'" in compat
    assert 'aplicación exclusiva para Windows' in compat


def test_no_alternate_desktop_shell_routes():
    assert not (ROOT / 'core' / 'update_manager.py').exists()
    assert not (ROOT / 'gui' / 'update_dialog.py').exists()
    stable = (ROOT / 'gui' / 'stable_scroll.py').read_text(encoding='utf-8')
    assert '<Button-' + '4>' not in stable
    assert '<Button-' + '5>' not in stable


def test_runtime_requirements_are_windows_native_sets():
    for name in ('requirements-runtime-flex.txt', 'requirements-base.txt', 'requirements-sensors.txt'):
        text = (ROOT / name).read_text(encoding='utf-8')
        assert 'platform_system' not in text
