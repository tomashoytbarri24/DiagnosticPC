"""Quality Gate reproducible de CorePulse.

No modifica Windows ni el estado del producto. Valida autoridad de versión,
sintaxis/compilación y la suite automatizada actual. Las pruebas históricas de
snapshot permanecen conservadas pero fuera del gate por defecto.
"""
from __future__ import annotations

import argparse
import compileall
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

from core.version import MIN_PYTHON, STAGE, VERSION, VERSION_LABEL

ROOT = Path(__file__).resolve().parent
RUNTIME_TARGETS = (
    ROOT / "main.py",
    ROOT / "bootstrap_corepulse.py",
    ROOT / "corepulse_launcher.py",
    ROOT / "core",
    ROOT / "gui",
    ROOT / "database",
    ROOT / "performance",
)


def _check(name: str, condition: bool, detail: str = "") -> bool:
    ok = bool(condition)
    suffix = f" — {detail}" if detail else ""
    print(f"[{'OK' if ok else 'FAIL'}] {name}{suffix}")
    return ok


def _metadata_checks() -> bool:
    checks: list[bool] = []
    checks.append(_check("Python compatible", sys.version_info[:2] >= MIN_PYTHON,
                         f"{sys.version_info.major}.{sys.version_info.minor}; política {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+"))
    checks.append(_check("VERSION numérica", VERSION.isdecimal(), VERSION_LABEL))
    checks.append(_check("STAGE definida", bool(STAGE), STAGE))

    latest = (ROOT / "LATEST_VERSION.txt").read_text(encoding="utf-8").strip()
    checks.append(_check("LATEST_VERSION sincronizado", latest == VERSION_LABEL, latest))

    readme_first = (ROOT / "README.md").read_text(encoding="utf-8-sig").splitlines()[0].strip()
    checks.append(_check("README sincronizado", readme_first == f"# CorePulse {VERSION_LABEL}", readme_first))

    versioning_first = (ROOT / "VERSIONING.md").read_text(encoding="utf-8-sig").splitlines()[0].strip()
    checks.append(_check("VERSIONING sincronizado", versioning_first == f"# Versión actual: {VERSION_LABEL}", versioning_first))

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject.get("project") or {}
    dynamic = project.get("dynamic") or []
    attr = (((pyproject.get("tool") or {}).get("setuptools") or {}).get("dynamic") or {}).get("version") or {}
    checks.append(_check("pyproject usa versión dinámica", "version" in dynamic and attr.get("attr") == "core.version.VERSION"))
    checks.append(_check("pyproject sin versión duplicada", "version" not in project))

    installer = (ROOT / "installer" / "CorePulse.iss").read_text(encoding="utf-8")
    checks.append(_check("Installer sin fallback de versión", '#define MyAppVersion "' not in installer and "#error MyAppVersion requerida" in installer))

    for build_name in ("build_exe.bat", "build_installer.bat"):
        text = (ROOT / build_name).read_text(encoding="utf-8")
        checks.append(_check(f"{build_name} sin fallback", "if not defined APPVER set" not in text and "Build cancelado" in text))
    return all(checks)


def _compile_runtime() -> bool:
    ok = True
    # compileall conserva su semántica real, pero redirige __pycache__ fuera del árbol fuente.
    old_prefix = sys.pycache_prefix
    with tempfile.TemporaryDirectory(prefix="corepulse-compile-") as cache_dir:
        sys.pycache_prefix = cache_dir
        try:
            for target in RUNTIME_TARGETS:
                if not target.exists():
                    ok = _check(f"Existe {target.name}", False, str(target)) and ok
                    continue
                if target.is_dir():
                    compiled = compileall.compile_dir(str(target), quiet=1, force=False)
                else:
                    compiled = compileall.compile_file(str(target), quiet=1, force=False)
                ok = _check(f"Compila {target.relative_to(ROOT)}", compiled) and ok
        finally:
            sys.pycache_prefix = old_prefix
    return ok


def _run_pytest(*, windows_real: bool) -> bool:
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    if windows_real:
        cmd.append("--run-windows-real")
    print("\n[RUN]", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT)
    return _check("Suite pytest actual", proc.returncode == 0, f"exit={proc.returncode}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quality Gate de CorePulse")
    parser.add_argument("--static-only", action="store_true", help="no ejecuta pytest")
    parser.add_argument("--windows-real", action="store_true", help="habilita pruebas marcadas windows_real")
    args = parser.parse_args(argv)

    print(f"CorePulse {VERSION_LABEL} — Quality Gate")
    print("=" * 64)
    ok = _metadata_checks()
    print("\nCompilación")
    print("-" * 64)
    ok = _compile_runtime() and ok
    if not args.static_only:
        print("\nPruebas")
        print("-" * 64)
        ok = _run_pytest(windows_real=args.windows_real) and ok
    print("\n" + "=" * 64)
    print("RESULTADO:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
