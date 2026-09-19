from __future__ import annotations

import importlib
import os
import platform
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(platform.system() != 'Linux', reason='validación específica Linux')
def test_linux_launch_gate_accepts_platform():
    from core.startup_readiness import collect_launch_gate
    from core.version import VERSION
    report = collect_launch_gate(VERSION)
    platform_item = next(item for item in report.items if item.id == 'platform')
    assert platform_item.ok
    assert 'Linux' in platform_item.label


@pytest.mark.skipif(platform.system() != 'Linux', reason='validación específica Linux')
def test_linux_sensor_provider_has_contract_and_real_cpu_name():
    from core.linux_sensor_provider import LinuxSensorProvider
    provider = LinuxSensorProvider()
    rows = provider.all_sensors()
    assert provider.name == 'Linux native sensors'
    assert isinstance(rows, list)
    assert provider.available is True
    cpu_rows = [row for row in rows if row.get('hardware_type') == 'Cpu']
    assert cpu_rows
    assert not str(cpu_rows[0].get('hardware_name') or '').isdigit()
    required = {'hardware_name','hardware_type','sensor_name','sensor_type','value','source'}
    assert required.issubset(cpu_rows[0])


@pytest.mark.skipif(platform.system() != 'Linux', reason='validación específica Linux')
def test_lhm_provider_dispatches_to_linux_native_provider():
    import core.lhm_provider as module
    module._PROVIDER = None
    provider = module.get_lhm_provider()
    assert provider.name == 'Linux native sensors'


@pytest.mark.skipif(platform.system() != 'Linux', reason='validación específica Linux')
def test_rtss_module_imports_without_winreg_on_linux():
    module = importlib.import_module('core.rtss_osd')
    assert module.IS_WINDOWS is False
    assert module.rtss_process_running() is False
    ok, detail = module.start_rtss()
    assert ok is False
    assert 'Windows' in detail


@pytest.mark.skipif(platform.system() != 'Linux', reason='validación específica Linux')
def test_linux_audio_backend_never_requires_windows_api():
    from core.audio_backend import AudioBackend
    backend = AudioBackend()
    devices = backend.devices()
    assert set(devices) == {'output', 'input'}
    for row in devices.values():
        assert 'available' in row
        assert 'name' in row


@pytest.mark.skipif(platform.system() != 'Linux', reason='validación específica Linux')
def test_linux_storage_health_has_list_contract():
    from core.storage_health_linux import get_linux_storage_health
    assert isinstance(get_linux_storage_health(), list)


def test_linux_requirements_exclude_windows_only_packages():
    text = (ROOT / 'requirements-linux.txt').read_text(encoding='utf-8').casefold()
    for forbidden in ('pywin32', 'pythonnet', 'hardwaremonitor', '\nwmi'):
        assert forbidden not in text


def test_linux_scripts_and_documentation_exist():
    for name in ('Instalar_CorePulse_Linux.sh', 'Ejecutar_CorePulse_Linux.sh', 'LINUX.md'):
        assert (ROOT / name).is_file()
    if os.name != 'nt':
        assert os.access(ROOT / 'Instalar_CorePulse_Linux.sh', os.X_OK)
        assert os.access(ROOT / 'Ejecutar_CorePulse_Linux.sh', os.X_OK)


def test_linux_ui_hides_windows_only_features_instead_of_marking_na():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    health = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    assert 'Gaming · N/A en Linux' not in main
    assert 'Tweaks Windows 11 · N/A' not in main
    assert "'Tweaks Windows 11' if platform.system() == 'Windows' else 'Ajustes Linux'" in dashboard
    assert "if platform.system() == 'Windows':" in health


def test_current_version_authority_is_generic():
    from core.version import VERSION, STAGE
    assert VERSION.isdecimal()
    assert bool(STAGE)
