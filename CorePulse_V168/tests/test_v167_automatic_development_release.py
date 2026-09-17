from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import subprocess
import zipfile


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(['git', '-C', str(repo), *args], text=True, capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def _repo(tmp_path: Path):
    repo = tmp_path / 'DiagnosticPC-Maxi'
    remote = tmp_path / 'remote.git'
    subprocess.check_call(['git', 'init', '-b', 'main', str(repo)], stdout=subprocess.DEVNULL)
    subprocess.check_call(['git', 'init', '--bare', str(remote)], stdout=subprocess.DEVNULL)
    _git(repo, 'config', 'user.name', 'Maxi')
    _git(repo, 'config', 'user.email', 'maxi@example.invalid')
    (repo / 'CorePulse_V167').mkdir()
    (repo / 'CorePulse_V167' / 'main.py').write_text('print("ok")\n', encoding='utf-8')
    for name in ('FASE 1', 'FASE 2', 'FASE 3'):
        (repo / name).mkdir()
        (repo / name / 'keep.txt').write_text(name, encoding='utf-8')
    _git(repo, 'add', '-A')
    _git(repo, 'commit', '-m', 'base')
    _git(repo, 'branch', '-M', 'maxi/corepulse-dev')
    _git(repo, 'remote', 'add', 'origin', str(remote))
    _git(repo, 'push', '-u', 'origin', 'maxi/corepulse-dev')
    profile = {
        'id': 'maxi', 'name': 'Maxi', 'repo_root': str(repo), 'remote': 'origin',
        'remote_url': str(remote), 'branch': 'maxi/corepulse-dev',
        'git_user_name': 'Maxi', 'git_user_email': 'maxi@example.invalid',
    }
    return repo, remote, profile


def test_workflow_is_version_agnostic_and_uses_one_prerelease_per_version():
    from core.development_release_automation import WORKFLOW_TEMPLATE
    assert "'**/corepulse-dev'" in WORKFLOW_TEMPLATE
    assert 'permissions:' in WORKFLOW_TEMPLATE and 'contents: write' in WORKFLOW_TEMPLATE
    assert 'V${VERSION}-dev' in WORKFLOW_TEMPLATE
    assert 'gh release upload' in WORKFLOW_TEMPLATE
    assert '--clobber' in WORKFLOW_TEMPLATE
    assert '--prerelease' in WORKFLOW_TEMPLATE
    assert 'CorePulse_V${VERSION}.zip' in WORKFLOW_TEMPLATE
    assert '.sha256' in WORKFLOW_TEMPLATE
    assert 'tomashoytbarri24' not in WORKFLOW_TEMPLATE
    assert 'maxicpa' not in WORKFLOW_TEMPLATE


def test_profile_publisher_bootstraps_root_workflow_and_pushes_it(tmp_path):
    from core.developer_publisher import inspect_profile_publish_context, publish_profile_root
    from core.development_release_automation import WORKFLOW_RELATIVE_PATH, WORKFLOW_MARKER

    repo, remote, profile = _repo(tmp_path)
    ctx = inspect_profile_publish_context(profile)
    assert WORKFLOW_RELATIVE_PATH.as_posix() in ctx['planned_files']
    assert ctx['development_release_automation'] is True
    result = publish_profile_root(profile, 'Enable automatic development release', expected_context=ctx)
    assert result['ok'] is True
    path = repo / WORKFLOW_RELATIVE_PATH
    assert path.is_file()
    assert WORKFLOW_MARKER in path.read_text(encoding='utf-8')
    assert _git(repo, 'status', '--porcelain') == ''
    remote_tree = subprocess.check_output(
        ['git', '--git-dir', str(remote), 'ls-tree', '-r', '--name-only', 'maxi/corepulse-dev'],
        text=True,
    ).splitlines()
    assert WORKFLOW_RELATIVE_PATH.as_posix() in remote_tree


def test_clean_package_builder_excludes_local_state_and_hash_matches(tmp_path):
    root = tmp_path / 'CorePulse_V167'
    (root / 'core').mkdir(parents=True)
    (root / 'core' / 'version.py').write_text('VERSION = "167"\n', encoding='utf-8')
    (root / 'main.py').write_text('print("ok")\n', encoding='utf-8')
    (root / '.env').write_text('SECRET=x\n', encoding='utf-8')
    (root / 'data').mkdir()
    (root / 'data' / 'private.json').write_text('{}', encoding='utf-8')
    (root / '__pycache__').mkdir()
    (root / '__pycache__' / 'x.pyc').write_bytes(b'bad')
    (root / 'assets').mkdir()
    (root / 'assets' / 'ok.txt').write_text('asset', encoding='utf-8')

    script = Path(__file__).resolve().parents[1] / 'tools' / 'release' / 'build_dev_package.py'
    spec = importlib.util.spec_from_file_location('build_dev_package', script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    result = mod.build(root, tmp_path / 'out')

    zpath = Path(result['zip'])
    with zipfile.ZipFile(zpath) as z:
        names = set(z.namelist())
    assert 'CorePulse_V167/main.py' in names
    assert 'CorePulse_V167/assets/ok.txt' in names
    assert 'CorePulse_V167/.env' not in names
    assert 'CorePulse_V167/data/private.json' not in names
    assert not any('__pycache__' in name for name in names)
    digest = hashlib.sha256(zpath.read_bytes()).hexdigest()
    assert digest == result['sha256']
    assert Path(result['sha256_file']).read_text(encoding='utf-8').strip() == f'{digest}  CorePulse_V167.zip'
