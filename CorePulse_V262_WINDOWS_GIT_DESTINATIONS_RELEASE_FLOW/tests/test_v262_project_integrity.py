from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_current_version_and_benchmark_identity():
    version = (ROOT / 'core' / 'version.py').read_text(encoding='utf-8')
    bench = (ROOT / 'core' / 'benchmark_version.py').read_text(encoding='utf-8')
    assert 'VERSION = "262"' in version
    assert 'GPU_BENCHMARK_VERSION = 25' in bench
    assert 'REAL_OR_NA' in (ROOT / 'COREPULSE_CANONICAL_BASE.md').read_text(encoding='utf-8')


def test_requested_v262_ui_contracts():
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


def test_v262_scroll_contracts_and_storage_alignment():
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




def test_v262_publish_ui_and_action_templates():
    update = (ROOT / 'gui' / 'update_dialog.py').read_text(encoding='utf-8')
    publisher = (ROOT / 'core' / 'developer_publisher.py').read_text(encoding='utf-8')
    assert 'Enviar a' in update
    assert 'Estable · {branch}' in update
    assert 'Desarrollo · {branch}' in update
    assert 'Publicar versión estable' in update
    assert 'target_branch=target_branch' in update
    assert 'STABLE_BRANCHES = {"main", "master", "trunk"}' in publisher
    assert 'discover_remote_branches' in publisher
    assert 'classify_destination_branch' in publisher
    assert 'force-push' in publisher
    dev = ROOT / 'developer' / 'github_actions_templates' / 'corepulse-development-release.yml'
    stable = ROOT / 'developer' / 'github_actions_templates' / 'corepulse-stable-release.yml'
    assert dev.exists() and stable.exists()
    assert "'**/corepulse-dev'" in dev.read_text(encoding='utf-8')
    assert '- main' in stable.read_text(encoding='utf-8')


def test_v262_remote_branch_publish_preserves_local_checkout(tmp_path, monkeypatch):
    import subprocess
    import core.developer_publisher as pub

    def git(repo, *args, check=True):
        return subprocess.run(
            ['git', '-C', str(repo), *args], check=check,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    remote = tmp_path / 'remote.git'
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    repo = tmp_path / 'DiagnosticPC'
    repo.mkdir()
    subprocess.run(['git', 'init', '-b', 'main', str(repo)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    git(repo, 'config', 'user.email', 'corepulse-test@example.invalid')
    git(repo, 'config', 'user.name', 'CorePulse Test')
    (repo / '.github' / 'workflows').mkdir(parents=True)
    (repo / '.github' / 'workflows' / 'dev.yml').write_text(
        "on:\n  push:\n    branches:\n      - '**/corepulse-dev'\n", encoding='utf-8'
    )
    for phase in ('FASE 1', 'FASE 2', 'FASE 3'):
        folder = repo / phase
        folder.mkdir()
        (folder / 'keep.txt').write_text(f'{phase} original\n', encoding='utf-8')
    old = repo / 'CorePulse_V257_WINDOWS_PROJECT_CLEANUP'
    (old / 'core').mkdir(parents=True)
    (old / 'main.py').write_text('print("old")\n', encoding='utf-8')
    (old / 'core' / 'version.py').write_text('VERSION = "257"\n', encoding='utf-8')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'initial main')
    git(repo, 'remote', 'add', 'origin', str(remote))
    git(repo, 'push', '-u', 'origin', 'main')

    git(repo, 'checkout', '-b', 'maxi/corepulse-dev')
    (repo / 'dev-only.txt').write_text('dev branch\n', encoding='utf-8')
    git(repo, 'add', 'dev-only.txt')
    git(repo, 'commit', '-m', 'dev marker')
    git(repo, 'push', '-u', 'origin', 'maxi/corepulse-dev')

    source = tmp_path / 'CorePulse_V262_WINDOWS_GIT_DESTINATIONS_RELEASE_FLOW'
    (source / 'core').mkdir(parents=True)
    (source / 'main.py').write_text('print("V262")\n', encoding='utf-8')
    (source / 'core' / 'version.py').write_text('VERSION = "262"\n', encoding='utf-8')
    (source / 'payload.txt').write_text('payload\n', encoding='utf-8')
    monkeypatch.setattr(pub, 'source_root', lambda: source)

    # Un cambio ajeno queda staged localmente y no debe entrar al commit remoto.
    (repo / 'FASE 1' / 'keep.txt').write_text('cambio local staged\n', encoding='utf-8')
    git(repo, 'add', 'FASE 1/keep.txt')
    head_before = git(repo, 'rev-parse', 'HEAD').stdout.strip()
    staged_before = git(repo, 'diff', '--cached', '--name-only').stdout.strip()

    ctx = pub.inspect_publish_context(repo, target_branch='main')
    assert ctx['can_publish'] is True
    assert ctx['branch'] == 'main'
    assert ctx['local_branch'] == 'maxi/corepulse-dev'
    assert ctx['destination_kind'] == 'stable'
    assert ctx['release_label'] == 'V262'

    result = pub.publish_current_version(
        repo, 'V262 test publish', target_branch='main', expected_context=ctx
    )
    assert result['ok'] is True
    assert result['branch'] == 'main'
    assert git(repo, 'branch', '--show-current').stdout.strip() == 'maxi/corepulse-dev'
    assert git(repo, 'rev-parse', 'HEAD').stdout.strip() == head_before
    assert git(repo, 'diff', '--cached', '--name-only').stdout.strip() == staged_before

    # Main remoto contiene V262, pero conserva FASE/.github/versiones anteriores.
    git(repo, 'fetch', 'origin', 'main')
    tree = git(repo, 'ls-tree', '-r', '--name-only', 'origin/main').stdout.splitlines()
    assert 'CorePulse_V262_WINDOWS_GIT_DESTINATIONS_RELEASE_FLOW/main.py' in tree
    assert 'CorePulse_V257_WINDOWS_PROJECT_CLEANUP/main.py' in tree
    assert '.github/workflows/dev.yml' in tree
    assert 'FASE 1/keep.txt' in tree
    remote_phase = git(repo, 'show', 'origin/main:FASE 1/keep.txt').stdout
    assert remote_phase == 'FASE 1 original\n'

    # La rama de desarrollo remota no se movió ni recibió la nueva versión.
    git(repo, 'fetch', 'origin', 'maxi/corepulse-dev')
    dev_tree = git(repo, 'ls-tree', '-r', '--name-only', 'origin/maxi/corepulse-dev').stdout.splitlines()
    assert 'CorePulse_V262_WINDOWS_GIT_DESTINATIONS_RELEASE_FLOW/main.py' not in dev_tree
