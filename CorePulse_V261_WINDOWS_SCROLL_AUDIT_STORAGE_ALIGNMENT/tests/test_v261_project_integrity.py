from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_current_version_and_benchmark_identity():
    version = (ROOT / 'core' / 'version.py').read_text(encoding='utf-8')
    bench = (ROOT / 'core' / 'benchmark_version.py').read_text(encoding='utf-8')
    assert 'VERSION = "261"' in version
    assert 'GPU_BENCHMARK_VERSION = 25' in bench
    assert 'REAL_OR_NA' in (ROOT / 'COREPULSE_CANONICAL_BASE.md').read_text(encoding='utf-8')


def test_requested_v261_ui_contracts():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    health = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    assert 'app._header_agent_frame = None' in dashboard
    assert "if 'visual_benchmark' in self._jobs or isinstance(self._visual_bench, dict):" in health
    assert "backend='canvas', wheel_pixels=96" in health
    assert "'Descargar todo'" in health
    assert "'Instalar todo'" in health
    assert "'Ver inventario'" in health


def test_driver_direct_contract():
    text = (ROOT / 'core' / 'driver_updates.py').read_text(encoding='utf-8')
    assert 'Microsoft Update Catalog directo' in text
    assert 'Windows Update Agent' in text  # explicit documentation that it is not used
    assert 'pnputil' in text.lower()
    assert 'download_all_driver_updates' in text
    assert 'install_all_driver_updates' in text


def test_required_runtime_assets_remain():
    required = [
        ROOT / 'main.py',
        ROOT / 'corepulse_launcher.py',
        ROOT / 'assets' / 'CorePulseIcon.png',
        ROOT / 'assets' / 'app_icon.ico',
        ROOT / 'tools' / 'presentmon' / 'PresentMon.exe',
        ROOT / 'build' / 'CorePulse.spec',
        ROOT / 'build' / 'runtime_hooks' / 'corepulse_frozen_runtime.py',
        ROOT / 'Instalar_Speedtest_Ookla.bat',
    ]
    assert all(path.exists() for path in required)


def test_obsolete_runtime_files_are_removed():
    removed = [
        ROOT / 'bootstrap_corepulse.py',
        ROOT / 'CorePulse_Bootstrap.bat',
        ROOT / 'core' / 'source_runtime_bootstrap.py',
        ROOT / 'core' / 'runtime_venv_path.py',
        ROOT / 'core' / 'tweak_apply_helper.py',
        ROOT / 'core' / 'tweak_rollback_helper.py',
        ROOT / 'core' / 'visual_benchmark.py',
        ROOT / 'core' / 'storage_health_linux.py',
    ]
    assert not any(path.exists() for path in removed)


def test_no_historical_runner_clutter():
    assert not list(ROOT.glob('Probar_Benchmark_GPU_V*.bat'))
    assert not list((ROOT / 'tools').glob('probar_benchmark_gpu_v*.py'))


def test_v261_scroll_contracts_and_storage_alignment():
    stable = (ROOT / 'gui' / 'stable_scroll.py').read_text(encoding='utf-8')
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    hardware = (ROOT / 'gui' / 'hardware_storage_view.py').read_text(encoding='utf-8')
    gui_text = "\n".join(path.read_text(encoding='utf-8', errors='ignore') for path in (ROOT / 'gui').glob('*.py'))
    assert 'wheel_pixels=96' in stable
    assert 'scroll_hold_ms=150' in stable
    assert 'CTkScrollableFrame(' not in gui_text
    assert "action_slot, text=badge_text" in dashboard
    assert "action_place={'relx': 1.0, 'rely': 0.5, 'anchor': 'e'}" in dashboard
    assert "if getattr(card, '_corepulse_storage_v238', False):" in hardware

