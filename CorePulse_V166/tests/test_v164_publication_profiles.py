from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def _repo(tmp_path: Path):
    repo = tmp_path / "DiagnosticPC-Maxi"
    remote = tmp_path / "remote.git"
    subprocess.check_call(["git", "init", "-b", "main", str(repo)], stdout=subprocess.DEVNULL)
    subprocess.check_call(["git", "init", "--bare", str(remote)], stdout=subprocess.DEVNULL)
    _git(repo, "config", "user.name", "Maxi")
    _git(repo, "config", "user.email", "maxi@example.invalid")
    for name in ("FASE 1", "FASE 2", "FASE 3"):
        p = repo / name
        p.mkdir()
        (p / "keep.txt").write_text(name, encoding="utf-8")
    core = repo / "CorePulse_V163"
    core.mkdir()
    (core / "main.py").write_text("old\n", encoding="utf-8")
    (repo / ".gitignore").write_text("ignored.tmp\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    _git(repo, "branch", "-M", "maxi/corepulse-dev")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-u", "origin", "maxi/corepulse-dev")
    return repo, remote


def _profile(repo: Path, remote: Path):
    return {
        "id": "maxi-test",
        "name": "Maxi",
        "repo_root": str(repo),
        "remote": "origin",
        "remote_url": str(remote),
        "branch": "maxi/corepulse-dev",
        "git_user_name": "Maxi",
        "git_user_email": "maxi@example.invalid",
    }


def test_v164_version_contract():
    from core.version import VERSION, STAGE
    assert VERSION == "166"
    assert STAGE == "UPDATE_LAYOUT_AND_PUBLISH_COUNT_CLARITY"


def test_profiles_are_local_configuration_without_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("COREPULSE_CONFIG_DIR", str(tmp_path / "config"))
    from core.publication_profiles import save_publication_profile, load_publication_profiles

    repo, remote = _repo(tmp_path)
    saved = save_publication_profile(_profile(repo, remote))
    assert saved["name"] == "Maxi"
    payload = load_publication_profiles()
    assert payload["active_profile_id"] == saved["id"]
    serialized = json.dumps(payload).casefold()
    assert "token" not in serialized
    assert "password" not in serialized
    assert "credential" not in serialized


def test_root_scope_publishes_only_real_git_changes_including_phases(tmp_path):
    from core.developer_publisher import inspect_profile_publish_context, publish_profile_root

    repo, remote = _repo(tmp_path)
    profile = _profile(repo, remote)
    (repo / "CorePulse_V163" / "main.py").write_text("new\n", encoding="utf-8")
    (repo / "FASE 1" / "keep.txt").write_text("phase changed\n", encoding="utf-8")
    (repo / "FASE 2" / "new.txt").write_text("new file\n", encoding="utf-8")
    (repo / "FASE 3" / "keep.txt").unlink()
    (repo / "ignored.tmp").write_text("must stay ignored\n", encoding="utf-8")

    ctx = inspect_profile_publish_context(profile)
    assert ctx["can_publish"] is True, ctx["blockers"]
    assert ctx["can_push"] is True
    assert set(ctx["planned_files"]) == {
        "CorePulse_V163/main.py", "FASE 1/keep.txt", "FASE 2/new.txt", "FASE 3/keep.txt"
    }
    assert "ignored.tmp" not in ctx["planned_files"]

    result = publish_profile_root(profile, "CorePulse V164 root publication", expected_context=ctx)
    assert result["ok"] is True
    assert _git(repo, "status", "--porcelain") == ""
    remote_tree = subprocess.check_output(
        ["git", "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "maxi/corepulse-dev"],
        text=True,
    ).splitlines()
    assert "FASE 2/new.txt" in remote_tree
    assert "FASE 3/keep.txt" not in remote_tree
    assert "ignored.tmp" not in remote_tree


def test_no_changes_disables_unnecessary_publication(tmp_path):
    from core.developer_publisher import inspect_profile_publish_context

    repo, remote = _repo(tmp_path)
    ctx = inspect_profile_publish_context(_profile(repo, remote))
    assert ctx["can_publish"] is True
    assert ctx["planned_count"] == 0
    assert ctx["can_push"] is False


def test_main_remains_blocked_for_profile_publication(tmp_path):
    from core.developer_publisher import inspect_profile_publish_context

    repo, remote = _repo(tmp_path)
    _git(repo, "switch", "-c", "main-v164-temp")
    # A profile may not target the actual main branch even if it is typed manually.
    profile = _profile(repo, remote)
    profile["branch"] = "main"
    ctx = inspect_profile_publish_context(profile)
    assert ctx["can_publish"] is False
    assert any("bloquead" in item.casefold() for item in ctx["blockers"])
