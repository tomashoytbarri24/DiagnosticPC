from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _make_repo(tmp_path: Path, name: str = "Any-Clone-Name") -> tuple[Path, Path]:
    repo = tmp_path / name
    remote = tmp_path / "remote.git"
    subprocess.check_call(["git", "init", "-b", "main", str(repo)], stdout=subprocess.DEVNULL)
    subprocess.check_call(["git", "init", "--bare", str(remote)], stdout=subprocess.DEVNULL)
    _git(repo, "config", "user.name", "CorePulse Test")
    _git(repo, "config", "user.email", "corepulse@example.invalid")
    for folder in ("FASE 1", "FASE 2", "FASE 3"):
        path = repo / folder
        path.mkdir()
        (path / "keep.txt").write_text(folder, encoding="utf-8")
    old = repo / "CorePulse_V136"
    old.mkdir()
    (old / "main.py").write_text("old\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "switch", "-c", "maxi/corepulse-v128")
    return repo, remote


def test_v154_contract_and_ui_semantics():
    ns = {}
    exec((ROOT / "core/version.py").read_text(encoding="utf-8"), ns)
    assert ns["VERSION"] == "154"
    assert ns["STAGE"] == "REPOSITORY_BRANCH_PUBLICATION_ARCHITECTURE"

    ui = (ROOT / "gui/update_dialog.py").read_text(encoding="utf-8")
    assert "REPOSITORIO LOCAL" in ui
    assert "Rama destino" in ui
    assert "Destino remoto" in ui
    assert "Versión a publicar" in ui
    assert 'f"Destino  {ctx.get(' not in ui


def test_github_remote_branch_url():
    from core.developer_publisher import remote_branch_url

    expected = "https://github.com/tomashoytbarri24/DiagnosticPC/tree/maxi/corepulse-v128"
    assert remote_branch_url(
        "https://github.com/tomashoytbarri24/DiagnosticPC.git",
        "maxi/corepulse-v128",
    ) == expected
    assert remote_branch_url(
        "git@github.com:tomashoytbarri24/DiagnosticPC.git",
        "maxi/corepulse-v128",
    ) == expected


def test_context_separates_repo_remote_branch_and_publish_folder(tmp_path, monkeypatch):
    import core.developer_publisher as publisher

    repo, _remote = _make_repo(tmp_path, name="Tomas-Puede-Llamarlo-Como-Quiera")
    src = tmp_path / "extracted-current-version"
    src.mkdir()
    (src / "main.py").write_text("v154\n", encoding="utf-8")
    monkeypatch.setattr(publisher, "source_root", lambda: src)

    ctx = publisher.inspect_publish_context(repo)
    assert ctx["can_publish"] is True, ctx["blockers"]
    assert Path(ctx["repo_root"]) == repo
    assert ctx["branch"] == "maxi/corepulse-v128"
    assert ctx["remote"] == str(_remote)
    assert ctx["publish_folder"] == "CorePulse_V154"
    assert ctx["publish_folder"] != repo.name


def test_publish_syncs_corepulse_inside_checkout_and_pushes_branch(tmp_path, monkeypatch):
    import core.developer_publisher as publisher

    repo, remote = _make_repo(tmp_path, name="DifferentLocalFolderName")
    src = tmp_path / "CorePulse-executed-somewhere-else"
    src.mkdir()
    (src / "main.py").write_text("v154 current\n", encoding="utf-8")
    monkeypatch.setattr(publisher, "source_root", lambda: src)

    result = publisher.publish_current_version(repo, "CorePulse V154 architecture")
    assert result["ok"] is True
    assert result["repo_root"] == str(repo.resolve())
    assert result["branch"] == "maxi/corepulse-v128"
    assert result["publish_folder"] == "CorePulse_V154"
    assert result["release_assets"] == {}

    # El checkout NO se sube como una carpeta anidada; su contenido es la raíz
    # de la rama y CorePulse queda como una carpeta versionada dentro de ella.
    tree = set(_git(repo, "ls-tree", "-d", "--name-only", "HEAD").splitlines())
    assert "CorePulse_V154" in tree
    assert "CorePulse_V136" not in tree
    assert repo.name not in tree
    for folder in ("FASE 1", "FASE 2", "FASE 3"):
        assert folder in tree
        assert (repo / folder / "keep.txt").read_text(encoding="utf-8") == folder

    remote_tree = set(
        subprocess.check_output(
            ["git", "--git-dir", str(remote), "ls-tree", "-d", "--name-only", "maxi/corepulse-v128"],
            text=True,
        ).splitlines()
    )
    assert "CorePulse_V154" in remote_tree
    assert "CorePulse_V136" not in remote_tree
    assert repo.name not in remote_tree


def test_untracked_backup_moves_only_once(tmp_path):
    import core.developer_publisher as publisher

    target = tmp_path / "CorePulse_V154"
    target.mkdir()
    (target / "x.txt").write_text("draft", encoding="utf-8")
    old_data_path = publisher.data_path
    try:
        publisher.data_path = lambda *parts: tmp_path / "appdata" / Path(*parts)
        backup = publisher._backup_untracked_target(target)
    finally:
        publisher.data_path = old_data_path
    assert not target.exists()
    assert (backup / "x.txt").read_text(encoding="utf-8") == "draft"
