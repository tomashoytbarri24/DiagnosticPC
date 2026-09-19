from __future__ import annotations
import shutil, subprocess
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
    return repo

def test_v152_contract():
    ns = {}; exec((ROOT / "core/version.py").read_text(encoding="utf-8"), ns)
    assert str(ns["VERSION"]).isdigit()
    assert bool(ns["STAGE"])
    ui = (ROOT / "gui/update_dialog.py").read_text(encoding="utf-8")
    assert "outer.grid_rowconfigure(3, weight=1)" in ui
    assert "outer.grid_rowconfigure(5, weight=1)" not in ui

def test_identical_existing_target_is_publishable(tmp_path, monkeypatch):
    import core.developer_publisher as publisher
    repo = _repo(tmp_path)
    src = tmp_path / "source"; src.mkdir(); (src / "main.py").write_text("new\n", encoding="utf-8")
    (src / "core").mkdir(); (src / "core" / "version.py").write_text('VERSION="152"\n', encoding="utf-8")
    target = repo / publisher.TARGET_FOLDER
    shutil.copytree(src, target)
    monkeypatch.setattr(publisher, "source_root", lambda: src)
    ctx = publisher.inspect_publish_context(repo)
    assert ctx["can_publish"] is True, ctx["blockers"]
    assert ctx["target_existing_state"] == "same"

def test_different_existing_target_blocks(tmp_path, monkeypatch):
    import core.developer_publisher as publisher
    repo = _repo(tmp_path)
    src = tmp_path / "source"; src.mkdir(); (src / "main.py").write_text("new\n", encoding="utf-8")
    target = repo / publisher.TARGET_FOLDER; target.mkdir(); (target / "main.py").write_text("LOCAL EDIT\n", encoding="utf-8")
    monkeypatch.setattr(publisher, "source_root", lambda: src)
    ctx = publisher.inspect_publish_context(repo)
    assert ctx["can_publish"] is False
    assert ctx["target_existing_state"] == "different"
    assert any("difiere" in b for b in ctx["blockers"])
