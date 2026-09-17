from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "clone-name-does-not-matter"
    remote = tmp_path / "remote.git"
    subprocess.check_call(["git", "init", "-b", "main", str(repo)], stdout=subprocess.DEVNULL)
    subprocess.check_call(["git", "init", "--bare", str(remote)], stdout=subprocess.DEVNULL)
    _git(repo, "config", "user.name", "CorePulse Test")
    _git(repo, "config", "user.email", "corepulse@example.invalid")
    for folder in ("FASE 1", "FASE 2", "FASE 3"):
        p = repo / folder
        p.mkdir()
        (p / "keep.txt").write_text(folder, encoding="utf-8")
    old = repo / "CorePulse_V136"
    old.mkdir()
    (old / "main.py").write_text("tracked old\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "switch", "-c", "maxi/corepulse-v128")
    _git(repo, "push", "-u", "origin", "maxi/corepulse-v128")
    return repo, remote


def test_v155_contract_and_exact_branch_url():
    ns = {}
    exec((ROOT / "core/version.py").read_text(encoding="utf-8"), ns)
    assert ns["VERSION"] == "155"
    assert ns["STAGE"] == "ROBUST_BRANCH_PUBLISH_WITH_LOCAL_PRESERVATION"

    from core.developer_publisher import remote_branch_url
    assert remote_branch_url(
        "https://github.com/tomashoytbarri24/DiagnosticPC.git",
        "maxi/corepulse-v128",
    ) == "https://github.com/tomashoytbarri24/DiagnosticPC/tree/maxi/corepulse-v128"


def test_dirty_old_corepulse_no_longer_blocks_and_is_preserved(tmp_path, monkeypatch):
    import core.developer_publisher as publisher

    repo, remote = _make_repo(tmp_path)
    old = repo / "CorePulse_V136"
    (old / "main.py").write_text("LOCAL WORK MUST SURVIVE\n", encoding="utf-8")
    (old / "notes.txt").write_text("local-only\n", encoding="utf-8")

    # Simula una copia V155 ya colocada en el clon pero distinta de la que se ejecuta.
    existing = repo / "CorePulse_V155"
    existing.mkdir()
    (existing / "main.py").write_text("stale local copy\n", encoding="utf-8")

    src = tmp_path / "CorePulse-running-elsewhere"
    src.mkdir()
    (src / "main.py").write_text("V155 CURRENT\n", encoding="utf-8")
    (src / "feature.py").write_text("ok = True\n", encoding="utf-8")
    monkeypatch.setattr(publisher, "source_root", lambda: src)
    monkeypatch.setattr(publisher, "data_path", lambda *parts: tmp_path / "appdata" / Path(*parts))

    ctx = publisher.inspect_publish_context(repo)
    assert ctx["can_publish"] is True, ctx["blockers"]
    assert "CorePulse_V136" in ctx["dirty_corepulse_preserved"]
    assert ctx["target_existing_state"] == "different_backup"

    result = publisher.publish_current_version(repo, "CorePulse V155 robust publish")
    assert result["ok"] is True
    assert result["branch"] == "maxi/corepulse-v128"
    assert result["publish_folder"] == "CorePulse_V155"
    assert result["target_backup"]

    # V136 sale de Git pero sigue físicamente con el trabajo local intacto.
    tree = set(_git(repo, "ls-tree", "-d", "--name-only", "HEAD").splitlines())
    assert "CorePulse_V136" not in tree
    assert "CorePulse_V155" in tree
    assert (old / "main.py").read_text(encoding="utf-8") == "LOCAL WORK MUST SURVIVE\n"
    assert (old / "notes.txt").read_text(encoding="utf-8") == "local-only\n"
    assert (repo / "CorePulse_V155" / "main.py").read_text(encoding="utf-8") == "V155 CURRENT\n"

    remote_tree = set(subprocess.check_output(
        ["git", "--git-dir", str(remote), "ls-tree", "-d", "--name-only", "maxi/corepulse-v128"],
        text=True,
    ).splitlines())
    assert "CorePulse_V136" not in remote_tree
    assert "CorePulse_V155" in remote_tree
    for folder in ("FASE 1", "FASE 2", "FASE 3"):
        assert folder in remote_tree
        assert (repo / folder / "keep.txt").read_text(encoding="utf-8") == folder


def test_staged_files_outside_corepulse_still_block(tmp_path, monkeypatch):
    import core.developer_publisher as publisher

    repo, _ = _make_repo(tmp_path)
    src = tmp_path / "source"
    src.mkdir()
    (src / "main.py").write_text("v155\n", encoding="utf-8")
    monkeypatch.setattr(publisher, "source_root", lambda: src)

    extra = repo / "README-local.txt"
    extra.write_text("do not include me", encoding="utf-8")
    _git(repo, "add", "README-local.txt")
    ctx = publisher.inspect_publish_context(repo)
    assert ctx["can_publish"] is False
    assert any("fuera de CorePulse" in item for item in ctx["blockers"])



def test_tracked_old_version_already_deleted_locally_still_publishes(tmp_path, monkeypatch):
    import core.developer_publisher as publisher

    repo, remote = _make_repo(tmp_path)
    old = repo / "CorePulse_V136"
    import shutil
    shutil.rmtree(old)

    src = tmp_path / "current"
    src.mkdir()
    (src / "main.py").write_text("V155 CURRENT\n", encoding="utf-8")
    monkeypatch.setattr(publisher, "source_root", lambda: src)

    ctx = publisher.inspect_publish_context(repo)
    assert ctx["can_publish"] is True, ctx["blockers"]
    assert "CorePulse_V136" in ctx["deletion_only_corepulse"]
    result = publisher.publish_current_version(repo, "publish V155 after manual old deletion")
    assert result["ok"] is True
    tree = set(_git(repo, "ls-tree", "-d", "--name-only", "HEAD").splitlines())
    assert "CorePulse_V136" not in tree
    assert "CorePulse_V155" in tree
    remote_tree = set(subprocess.check_output(
        ["git", "--git-dir", str(remote), "ls-tree", "-d", "--name-only", "maxi/corepulse-v128"],
        text=True,
    ).splitlines())
    assert "CorePulse_V136" not in remote_tree
    assert "CorePulse_V155" in remote_tree

def test_publish_ui_shows_real_branch_as_button_target():
    ui = (ROOT / "gui/update_dialog.py").read_text(encoding="utf-8")
    assert 'text=f"Publicar en {branch_label}"' in ui
    assert "Destino remoto" in ui
    assert "Versiones CorePulse anteriores con cambios locales se conservarán físicamente" in ui
