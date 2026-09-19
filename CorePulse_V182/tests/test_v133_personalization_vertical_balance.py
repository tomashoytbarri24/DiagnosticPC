"""V133 — Personalización balanceada en ventanas restauradas."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def test_v133_version_and_vertical_personalization_contract():
    version = (ROOT / "core" / "version.py").read_text(encoding="utf-8")
    layout = (ROOT / "gui" / "dashboard_layout.py").read_text(encoding="utf-8")
    assert 'VERSION = ' in version and 'VERSION_LABEL' in version
    assert 'PERSONALIZATION_VERTICAL_BALANCE' in version
    assert "personalization_tight = compact or viewport_h < 900" in layout
    assert "if personalization_tight:" in layout
    assert "hint.pack_forget()" in layout
    assert "divider.pack_forget()" in layout
    assert "ver.pack_forget()" in layout
    assert "height=33 if personalization_tight else 35" in layout
    assert "pady=(3, 5) if personalization_tight else (7, 7)" in layout


def test_ctkbutton_padding_guard_remains_valid():
    offenders = []
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "CTkButton":
                bad = sorted({kw.arg for kw in node.keywords if kw.arg} & {"padx", "pady"})
                if bad:
                    offenders.append((str(path.relative_to(ROOT)), node.lineno, bad))
    assert not offenders, offenders


def test_protected_files_unchanged():
    expected = {
        'core/runtime_venv_path.py': '263d725dc8a50ef57d2e0dd8d8827968f58d2b67dcee6b0a276ca6dd8d562e92',
        'bootstrap_corepulse.py': '925d4ef090b28c27ceffbbbba9362a8137f665212ac445e96a096c0ce5e17a0b',
        'core/source_runtime_bootstrap.py': 'bde37780c35ebc280b0b22ac6a71926051ae9fde48b65935b6af64b819f7ccfd',
        'requirements-runtime-lock.txt': '36ee044c5dab3c5c8cfecbe0456923c9f406d83a93ef04d93f9fd27f1566c706',
        'core/nvme_smart_windows.py': 'fe9481d270d5b47299b97fc97d37ee56f65bd904333f634255e4a91e63958283',
    }
    for rel, digest in expected.items():
        assert sha256(rel) == digest, rel
