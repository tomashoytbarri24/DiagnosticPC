from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_linux_package_has_one_click_launchers():
    desktop = ROOT / 'CorePulse_Linux.desktop'
    launcher = ROOT / 'CorePulse_Linux_Launcher.sh'
    simple = ROOT / 'CorePulse'
    assert desktop.is_file()
    assert launcher.is_file()
    assert simple.is_file()
    text = desktop.read_text(encoding='utf-8')
    assert 'Type=Application' in text
    assert 'Name=CorePulse' in text
    assert 'Terminal=false' in text
    assert 'CorePulse_Linux_Launcher.sh' in text


def test_linux_launcher_prepares_runtime_automatically_and_then_runs_gui():
    source = (ROOT / 'CorePulse_Linux_Launcher.sh').read_text(encoding='utf-8')
    assert 'runtime_ready()' in source
    assert 'launch_installer_terminal()' in source
    assert 'Instalar_CorePulse_Linux.sh' in source
    assert '.venv-linux/bin/python' in source
    assert 'corepulse_launcher.py' in source


def test_linux_installer_registers_menu_shortcut_and_stable_current_pointer():
    source = (ROOT / 'Instalar_CorePulse_Linux.sh').read_text(encoding='utf-8')
    assert 'applications' in source
    assert 'corepulse.desktop' in source
    assert 'icons/hicolor/256x256/apps' in source
    assert 'CorePulse/current' in source or 'CURRENT_LINK="$COREPULSE_HOME/current"' in source
    assert 'CorePulse ya puede abrirse sin comandos' in source


def test_linux_update_helper_relaunches_through_click_launcher():
    source = (ROOT / 'core' / 'update_manager.py').read_text(encoding='utf-8')
    assert 'CorePulse_Linux_Launcher.sh' in source
    assert 'current.symlink_to(root' in source
    assert 'start_new_session=True' in source


def test_version_authority_remains_dynamic_after_v176():
    from core.version import VERSION, STAGE
    assert VERSION.isdecimal()
    assert bool(STAGE)
