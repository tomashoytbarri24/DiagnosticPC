from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _make_clone_like_repo(base: Path) -> Path:
    repo = base / "DiagnosticPC-Maxi"
    remote = base / "DiagnosticPC-remote.git"
    subprocess.check_call(["git", "init", "-b", "main", str(repo)], stdout=subprocess.DEVNULL)
    subprocess.check_call(["git", "init", "--bare", str(remote)], stdout=subprocess.DEVNULL)
    _git(repo, "config", "user.name", "CorePulse Test")
    _git(repo, "config", "user.email", "corepulse@example.invalid")
    for name in ("FASE 1", "FASE 2", "FASE 3"):
        d = repo / name
        d.mkdir(parents=True)
        (d / "keep.txt").write_text(name, encoding="utf-8")
    old = repo / "CorePulse_V128"
    old.mkdir()
    (old / "main.py").write_text("print('old')\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "switch", "-c", "maxi/corepulse-v128")
    return repo


def test_v136_version_and_review_feedback_contract():
    ns = {}
    exec((ROOT / "core" / "version.py").read_text(encoding="utf-8"), ns)
    assert ns["VERSION"] == "136"
    assert ns["STAGE"] == "GIT_REPOSITORY_DISCOVERY_AND_REVIEW_FEEDBACK"
    ui = (ROOT / "gui" / "update_dialog.py").read_text(encoding="utf-8")
    assert 'text="Revisando…"' in ui
    assert "Revisión {checked_at}" in ui
    assert "clon Git detectado automáticamente" in ui
    assert "Repositorios Git cercanos detectados" in ui


def test_zip_copy_selection_finds_unambiguous_nearby_git_clone(tmp_path):
    import core.developer_publisher as publisher

    repo = _make_clone_like_repo(tmp_path)
    extracted = tmp_path / "DiagnosticPC-main" / "DiagnosticPC-main"
    extracted.mkdir(parents=True)
    for name in ("FASE 1", "FASE 2", "FASE 3"):
        (extracted / name).mkdir()

    ctx = publisher.inspect_publish_context(extracted)
    assert ctx["available"] is True
    assert ctx["can_publish"] is True
    assert Path(ctx["repo_root"]).resolve() == repo.resolve()
    assert ctx["branch"] == "maxi/corepulse-v128"
    assert ctx["auto_detected"] is True
    assert all(ctx["protected"].values())
    assert "detectó automáticamente" in ctx["resolution_note"]


def test_non_git_folder_explains_clone_requirement(tmp_path):
    import core.developer_publisher as publisher

    extracted = tmp_path / "solo-zip" / "DiagnosticPC-main"
    extracted.mkdir(parents=True)
    ctx = publisher.inspect_publish_context(extracted)
    assert ctx["available"] is False
    text = "\n".join(ctx["blockers"])
    assert ".git" in text
    assert "git clone" in text
