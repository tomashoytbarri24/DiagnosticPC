from __future__ import annotations
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _repo(tmp_path: Path):
    repo = tmp_path / "DiagnosticPC-Maxi"
    remote = tmp_path / "remote.git"
    subprocess.check_call(["git", "init", "-b", "main", str(repo)], stdout=subprocess.DEVNULL)
    subprocess.check_call(["git", "init", "--bare", str(remote)], stdout=subprocess.DEVNULL)
    _git(repo, "config", "user.name", "CorePulse Test")
    _git(repo, "config", "user.email", "corepulse@example.invalid")
    for name in ("FASE 1", "FASE 2", "FASE 3"):
        p = repo / name; p.mkdir(); (p / "keep.txt").write_text(name, encoding="utf-8")
    old = repo / "CorePulse_V136"; old.mkdir(); (old / "main.py").write_text("old\n", encoding="utf-8")
    _git(repo, "add", "."); _git(repo, "commit", "-m", "base")
    _git(repo, "remote", "add", "origin", str(remote)); _git(repo, "switch", "-c", "maxi/corepulse-v128")
    return repo, remote


def test_v153_contract():
    ns = {}; exec((ROOT / "core/version.py").read_text(encoding="utf-8"), ns)
    assert str(ns["VERSION"]).isdigit()
    assert bool(ns["STAGE"])
    src = (ROOT / "core/developer_publisher.py").read_text(encoding="utf-8")
    assert 'target_existing_state = "untracked_different"' in src
    assert "_backup_untracked_target" in src


def test_different_untracked_target_is_publishable(tmp_path, monkeypatch):
    import core.developer_publisher as publisher
    repo, _ = _repo(tmp_path)
    src = tmp_path / "source"; src.mkdir(); (src / "main.py").write_text("new\n", encoding="utf-8")
    target = repo / publisher.TARGET_FOLDER; target.mkdir(); (target / "main.py").write_text("old local copy\n", encoding="utf-8")
    monkeypatch.setattr(publisher, "source_root", lambda: src)
    ctx = publisher.inspect_publish_context(repo)
    assert ctx["can_publish"] is True, ctx["blockers"]
    assert ctx["target_existing_state"] == "untracked_different"


def test_publish_backs_up_untracked_target_and_replaces_old_version(tmp_path, monkeypatch):
    import core.developer_publisher as publisher
    repo, _ = _repo(tmp_path)
    src = tmp_path / "source"; src.mkdir(); (src / "main.py").write_text("new current version\n", encoding="utf-8")
    target = repo / publisher.TARGET_FOLDER; target.mkdir(); (target / "main.py").write_text("different local draft\n", encoding="utf-8")
    backup_root = tmp_path / "appdata"
    monkeypatch.setattr(publisher, "source_root", lambda: src)
    monkeypatch.setattr(publisher, "data_path", lambda *parts: backup_root.joinpath(*parts))
    monkeypatch.setattr(publisher, "_write_release_assets", lambda project_dir: {"zip": "test.zip", "sha256": "abc", "sha256_file": "test.sha256"})

    result = publisher.publish_current_version(repo, "publish v153")
    assert result["ok"] is True
    assert (repo / publisher.TARGET_FOLDER / "main.py").read_text(encoding="utf-8") == "new current version\n"
    assert not (repo / "CorePulse_V136").exists()
    assert _git(repo, "status", "--porcelain") == ""
    tree = _git(repo, "ls-tree", "-d", "--name-only", "HEAD").splitlines()
    assert publisher.TARGET_FOLDER in tree
    assert "CorePulse_V136" not in tree
    for name in ("FASE 1", "FASE 2", "FASE 3"):
        assert (repo / name / "keep.txt").read_text(encoding="utf-8") == name
    backup = Path(result["target_backup"])
    assert backup.is_dir()
    assert (backup / "main.py").read_text(encoding="utf-8") == "different local draft\n"


def test_staged_different_target_still_blocks(tmp_path, monkeypatch):
    import core.developer_publisher as publisher
    repo, _ = _repo(tmp_path)
    src = tmp_path / "source"; src.mkdir(); (src / "main.py").write_text("new\n", encoding="utf-8")
    target = repo / publisher.TARGET_FOLDER; target.mkdir(); (target / "main.py").write_text("staged local work\n", encoding="utf-8")
    _git(repo, "add", publisher.TARGET_FOLDER)
    monkeypatch.setattr(publisher, "source_root", lambda: src)
    ctx = publisher.inspect_publish_context(repo)
    assert ctx["can_publish"] is False
    assert ctx["target_existing_state"] == "different"
    assert any("cambios Git" in item for item in ctx["blockers"])
