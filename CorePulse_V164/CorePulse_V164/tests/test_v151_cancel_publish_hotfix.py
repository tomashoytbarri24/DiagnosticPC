from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _repo_with_old_version(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "DiagnosticPC-Maxi"
    remote = tmp_path / "remote.git"
    subprocess.check_call(["git", "init", "-b", "main", str(repo)], stdout=subprocess.DEVNULL)
    subprocess.check_call(["git", "init", "--bare", str(remote)], stdout=subprocess.DEVNULL)
    _git(repo, "config", "user.name", "CorePulse Test")
    _git(repo, "config", "user.email", "corepulse@example.invalid")
    for name in ("FASE 1", "FASE 2", "FASE 3"):
        p = repo / name
        p.mkdir()
        (p / "keep.txt").write_text(name, encoding="utf-8")
    old = repo / "CorePulse_V136"
    old.mkdir()
    (old / "main.py").write_text("print('v136')\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base v136")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "switch", "-c", "maxi/corepulse-v128")
    return repo, remote


def test_v151_version_and_hotfix_contract():
    ns = {}
    exec((ROOT / "core" / "version.py").read_text(encoding="utf-8"), ns)
    assert ns["VERSION"] == "151"
    assert ns["STAGE"] == "DIAGNOSTIC_CANCEL_AND_GIT_PUBLISH_HOTFIX"
    diag = (ROOT / "gui" / "diagnostic_view.py").read_text(encoding="utf-8")
    assert "text='Diagnosticar de nuevo'" in diag
    update = (ROOT / "gui" / "update_dialog.py").read_text(encoding="utf-8")
    assert "Versión registrada en Git:" in update
    assert "_apply_publish_density" in update


def test_deleted_old_corepulse_is_not_a_publish_blocker(tmp_path, monkeypatch):
    import core.developer_publisher as publisher

    repo, _remote = _repo_with_old_version(tmp_path)
    # Simula exactamente el caso real: HEAD aún registra V136, pero el usuario
    # ya borró esa carpeta de su working tree.
    subprocess.check_call(["git", "-C", str(repo), "rm", "-r", "--quiet", "--cached", "CorePulse_V136"])
    # Restauramos índice y borramos sólo físicamente para dejar ' D' unstaged.
    subprocess.check_call(["git", "-C", str(repo), "reset", "--quiet", "HEAD", "--", "CorePulse_V136"])
    old = repo / "CorePulse_V136"
    for child in old.rglob("*"):
        if child.is_file():
            child.unlink()
    old.rmdir()

    src = tmp_path / "source"
    src.mkdir()
    (src / "main.py").write_text("print('v151')\n", encoding="utf-8")
    monkeypatch.setattr(publisher, "source_root", lambda: src)

    ctx = publisher.inspect_publish_context(repo)
    assert ctx["can_publish"] is True, ctx["blockers"]
    assert "CorePulse_V136" in ctx["deletion_only_corepulse"]
    assert not any("podrían perderse" in b for b in ctx["blockers"])


def test_modified_old_corepulse_still_blocks(tmp_path, monkeypatch):
    import core.developer_publisher as publisher

    repo, _remote = _repo_with_old_version(tmp_path)
    (repo / "CorePulse_V136" / "main.py").write_text("local work\n", encoding="utf-8")
    src = tmp_path / "source"
    src.mkdir()
    (src / "main.py").write_text("print('v151')\n", encoding="utf-8")
    monkeypatch.setattr(publisher, "source_root", lambda: src)
    ctx = publisher.inspect_publish_context(repo)
    assert ctx["can_publish"] is False
    assert any("podrían perderse" in b for b in ctx["blockers"])


def test_cancelled_diagnostic_keeps_restart_action_visible():
    src = (ROOT / "gui" / "diagnostic_view.py").read_text(encoding="utf-8")
    section = src[src.index("def show_cancelled"):src.index("def _repeat")]
    assert "self.btn_cancel.configure" in section
    assert "command=self._repeat" in section
    assert "self.btn_cancel.grid()" in section
