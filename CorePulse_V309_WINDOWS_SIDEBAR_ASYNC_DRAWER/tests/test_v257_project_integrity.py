from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_current_version_and_benchmark_identity():
    version = (ROOT / 'core' / 'version.py').read_text(encoding='utf-8')
    bench = (ROOT / 'core' / 'benchmark_version.py').read_text(encoding='utf-8')
    assert 'VERSION = "309"' in version
    assert 'GPU_BENCHMARK_VERSION = 25' in bench
    assert 'REAL_OR_NA' in (ROOT / 'COREPULSE_CANONICAL_BASE.md').read_text(encoding='utf-8')


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
    ]
    assert not any(path.exists() for path in removed)


def test_no_historical_runner_clutter():
    assert not list(ROOT.glob('Probar_Benchmark_GPU_V*.bat'))
    assert not list((ROOT / 'tools').glob('probar_benchmark_gpu_v*.py'))
