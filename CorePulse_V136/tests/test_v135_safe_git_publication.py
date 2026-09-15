from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _init_repo(tmp_path: Path):
    repo = tmp_path / "DiagnosticPC"
    remote = tmp_path / "remote.git"
    repo.mkdir()
    subprocess.check_call(["git", "init", "-b", "main", str(repo)])
    subprocess.check_call(["git", "init", "--bare", str(remote)])
    _git(repo, "config", "user.name", "CorePulse Test")
    _git(repo, "config", "user.email", "corepulse@example.invalid")
    for name in ("FASE 1", "FASE 2", "FASE 3"):
        path = repo / name
        path.mkdir()
        (path / "keep.txt").write_text(name, encoding="utf-8")
    old = repo / "CorePulse_V134"
    old.mkdir()
    (old / "main.py").write_text("print('old')\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "remote", "add", "origin", str(remote))
    return repo, remote


def test_v135_version_and_publication_ui():
    ns = {}
    exec((ROOT / "core" / "version.py").read_text(encoding="utf-8"), ns)
    assert int(ns["VERSION"]) >= 135
    ui = (ROOT / "gui" / "update_dialog.py").read_text(encoding="utf-8")
    assert "Publicar versión" in ui
    assert "MENSAJE DEL COMMIT" in ui
    assert "Publicar en mi rama" in ui
    assert "FASE 1, FASE 2 y FASE 3" in ui


def test_main_is_blocked_and_protected_phases_are_required(tmp_path, monkeypatch):
    import core.developer_publisher as publisher

    repo, _remote = _init_repo(tmp_path)
    src = tmp_path / "source"
    src.mkdir()
    (src / "main.py").write_text("print('v135')\n", encoding="utf-8")
    monkeypatch.setattr(publisher, "source_root", lambda: src)

    ctx = publisher.inspect_publish_context(repo)
    assert not ctx["can_publish"]
    assert any("protegida" in item for item in ctx["blockers"])
    assert all(ctx["protected"].values())


def test_publication_replaces_only_corepulse_folder_and_pushes_branch(tmp_path, monkeypatch):
    import core.developer_publisher as publisher

    repo, remote = _init_repo(tmp_path)
    _git(repo, "switch", "-c", "maxi/v135-test")

    src = tmp_path / "source"
    (src / "core").mkdir(parents=True)
    (src / "main.py").write_text("print('v135')\n", encoding="utf-8")
    (src / "core" / "sample.py").write_text("VALUE = 135\n", encoding="utf-8")
    monkeypatch.setattr(publisher, "source_root", lambda: src)
    # Keep generated release assets inside the temporary test tree.
    out = tmp_path / "appdata"
    monkeypatch.setattr(publisher, "data_path", lambda *parts: out.joinpath(*parts))

    result = publisher.publish_current_version(repo, "CorePulse V135 - publicación segura")
    assert result["ok"] is True
    assert result["branch"] == "maxi/v135-test"
    assert (repo / publisher.TARGET_FOLDER / "main.py").is_file()
    assert not (repo / "CorePulse_V134").exists()
    for name in ("FASE 1", "FASE 2", "FASE 3"):
        assert (repo / name / "keep.txt").read_text(encoding="utf-8") == name

    names = _git(repo, "ls-tree", "-d", "--name-only", "HEAD").splitlines()
    assert publisher.TARGET_FOLDER in names
    assert "CorePulse_V134" not in names
    assert all(name in names for name in ("FASE 1", "FASE 2", "FASE 3"))
    assert _git(repo, "log", "-1", "--pretty=%B") == "CorePulse V135 - publicación segura"
    assert _git(remote, "branch", "--list", "maxi/v135-test")
    assert Path(result["release_assets"]["zip"]).is_file()
    assert Path(result["release_assets"]["sha256_file"]).is_file()
