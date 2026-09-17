"""Preparador autocontenido del entorno fuente de CorePulse para Windows.

No depende de paquetes externos. Crea/repara un venv de ruta corta, instala el runtime bloqueado,
verifica imports críticos y abre CorePulse con pythonw.exe. El usuario no necesita
ejecutar instalar_dependencias.bat manualmente.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import threading
import time
import traceback

from core.runtime_venv_path import source_runtime_venv

ROOT = Path(__file__).resolve().parent
VENV = source_runtime_venv(ROOT)
VENV_PY = VENV / "Scripts" / "python.exe"
VENV_PYW = VENV / "Scripts" / "pythonw.exe"
RUNTIME_LOCK = ROOT / "requirements-runtime-lock.txt"
LOG = ROOT / "runtime_bootstrap.log"
MARKER = VENV / ".corepulse_runtime.json"
PYVENV_CFG = VENV / "pyvenv.cfg"

REQUIRED_IMPORTS = (
    "psutil", "customtkinter", "PIL", "matplotlib", "platformdirs",
)
OPTIONAL_IMPORTS = (
    "reportlab", "send2trash", "dotenv", "pystray", "wmi",
    "win32api", "pythoncom", "pywintypes", "clr", "pythonnet",
)


def _log(text: str) -> None:
    try:
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")
    except Exception:
        pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(args, *, check=True) -> subprocess.CompletedProcess:
    _log("RUN " + " ".join(map(str, args)))
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    proc = subprocess.run(
        [str(x) for x in args],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    if proc.stdout:
        _log(proc.stdout.rstrip())
    if check and proc.returncode != 0:
        raise RuntimeError(f"Comando falló ({proc.returncode}): {' '.join(map(str, args))}")
    return proc


def _ensure_pip() -> tuple[bool, str]:
    """Garantiza que el venv tenga un pip utilizable sin depender de Internet.

    Python 3.12 crea venv con ensurepip; si pip falta o está roto, se repara
    primero con la copia embebida de Python. No actualiza paquetes aquí.
    """
    probe = _run([VENV_PY, "-m", "pip", "--version"], check=False)
    if probe.returncode == 0:
        return True, (probe.stdout or "").strip()

    _log("pip no utilizable; intentando ensurepip --upgrade")
    repair = _run([VENV_PY, "-m", "ensurepip", "--upgrade"], check=False)
    probe2 = _run([VENV_PY, "-m", "pip", "--version"], check=False)
    detail = "\n".join(x for x in ((repair.stdout or "").strip(), (probe2.stdout or "").strip()) if x)
    return probe2.returncode == 0, detail


def _install_runtime_lock() -> None:
    """Instala el runtime real con reintento y conserva detalle de error útil."""
    args = [
        VENV_PY, "-m", "pip", "install", "--disable-pip-version-check",
        "--prefer-binary", "--retries", "4", "--timeout", "45",
        "-r", str(RUNTIME_LOCK),
    ]
    first = _run(args, check=False)
    if first.returncode == 0:
        return

    _log("Primer intento de runtime falló; reintentando una vez")
    time.sleep(1.0)
    second = _run(args, check=False)
    if second.returncode == 0:
        return

    detail = (second.stdout or first.stdout or "sin detalle de pip").strip()
    if len(detail) > 1800:
        detail = detail[-1800:]
    raise RuntimeError(
        "No se pudieron instalar los componentes de CorePulse.\n\n"
        "El instalador local de Python funciona, pero la descarga/instalación "
        "del runtime falló. Comprueba Internet, proxy/antivirus y vuelve a abrir CorePulse.\n\n"
        f"Detalle de pip:\n{detail}"
    )


def _host_is_supported() -> tuple[bool, str]:
    bits = struct.calcsize("P") * 8
    ok = sys.version_info[:2] == (3, 12) and bits == 64
    return ok, f"Python {sys.version.split()[0]} · {bits}-bit · {sys.executable}"


def _venv_healthy() -> bool:
    # Un python.exe suelto dentro de Scripts NO convierte la carpeta en un venv.
    # En un runtime copiado/incompleto Windows puede llegar a ejecutar ese binario,
    # pero pip/ensurepip fallan después con "No pyvenv.cfg file".
    if not VENV_PY.is_file() or not PYVENV_CFG.is_file():
        return False
    try:
        proc = _run([
            VENV_PY, "-c",
            (
                "import pathlib,sys,struct; "
                "expected=pathlib.Path(sys.argv[1]).resolve(); "
                "prefix=pathlib.Path(sys.prefix).resolve(); "
                "base=pathlib.Path(sys.base_prefix).resolve(); "
                "ok=(sys.version_info[:2]==(3,12) and struct.calcsize('P')*8==64 "
                "and prefix==expected and base!=prefix); "
                "raise SystemExit(0 if ok else 5)"
            ),
            str(VENV),
        ], check=False)
        return proc.returncode == 0
    except Exception:
        return False


def _verify_imports() -> tuple[bool, str]:
    # Sólo el núcleo requerido puede bloquear el arranque. WMI/pythonnet/LHM y
    # demás capacidades siguen la política universal REAL_OR_NA y se auditan
    # como opcionales después.
    imports = ",".join(REQUIRED_IMPORTS)
    proc = _run([VENV_PY, "-c", f"import {imports}; print('core-runtime-ok')"], check=False)
    core_ok = proc.returncode == 0
    detail = (proc.stdout or "").strip()
    if not core_ok:
        return False, detail

    # Evitamos una expresión compleja dentro del -c: cada import opcional se
    # prueba de forma aislada y sólo se registra.
    for module in OPTIONAL_IMPORTS:
        op = _run([VENV_PY, "-c", f"import {module}"], check=False)
        if op.returncode != 0:
            _log(f"OPTIONAL N/A {module}: {(op.stdout or '').strip()}")
    lhm = _run([VENV_PY, "-c",
        "import HardwareMonitor,pathlib; from HardwareMonitor.Hardware import Computer; "
        "p=pathlib.Path(HardwareMonitor.__file__).resolve().parent/'lib'; "
        "assert list(p.rglob('LibreHardwareMonitorLib.dll')); assert list(p.rglob('HidSharp.dll'))"
    ], check=False)
    if lhm.returncode != 0:
        _log(f"OPTIONAL N/A HardwareMonitor: {(lhm.stdout or '').strip()}")
    return True, detail


def _marker_valid(lock_hash: str) -> bool:
    if not MARKER.is_file():
        return False
    try:
        data = json.loads(MARKER.read_text(encoding="utf-8"))
        return data.get("lock_sha256") == lock_hash and data.get("python") == "3.12-x64"
    except Exception:
        return False


def _write_marker(lock_hash: str) -> None:
    MARKER.write_text(json.dumps({
        "lock_sha256": lock_hash,
        "python": "3.12-x64",
        "ready": True,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _prepare(progress) -> None:
    if os.name != "nt":
        raise RuntimeError("El bootstrap automático de CorePulse está diseñado para Windows.")
    ok, detail = _host_is_supported()
    _log(detail)
    if not ok:
        raise RuntimeError(
            "CorePulse requiere Python 3.12 x64 para preparar automáticamente su entorno.\n\n"
            f"Detectado: {detail}"
        )
    if not RUNTIME_LOCK.is_file():
        raise RuntimeError("Falta requirements-runtime-lock.txt en la carpeta de CorePulse.")

    progress("Comprobando entorno local…", 0.10)
    _log(f"Runtime VENV corto: {VENV}")
    try:
        VENV.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError(f"No se pudo preparar la carpeta de runtime: {VENV}") from exc
    if not _venv_healthy():
        progress("Creando el entorno de CorePulse…", 0.22)
        try:
            if VENV.exists():
                shutil.rmtree(VENV, ignore_errors=False)
        except Exception as exc:
            raise RuntimeError(
                "No se pudo reemplazar el entorno anterior. Cierra cualquier CorePulse/Python que esté usando el runtime de CorePulse."
            ) from exc
        _run([sys.executable, "-m", "venv", str(VENV)])
        if not PYVENV_CFG.is_file() or not VENV_PY.is_file():
            raise RuntimeError(
                "Python no pudo crear un entorno virtual completo para CorePulse. "
                "Falta pyvenv.cfg o Scripts\\python.exe después de crear el runtime."
            )

    lock_hash = _sha256(RUNTIME_LOCK)
    progress("Verificando componentes de CorePulse…", 0.36)
    if _marker_valid(lock_hash):
        ready, _ = _verify_imports()
        if ready:
            progress("Entorno listo.", 1.0)
            return

    progress("Preparando instalador de componentes…", 0.48)
    pip_ok, pip_detail = _ensure_pip()
    if not pip_ok:
        raise RuntimeError(
            "El entorno local se creó, pero Python no pudo preparar pip.\n\n"
            f"Detalle: {pip_detail[-1200:] if pip_detail else 'sin detalle'}"
        )

    # No se hace un upgrade de pip/setuptools/wheel antes del runtime. El pip
    # incluido con Python 3.12 es suficiente para intentar los wheels bloqueados;
    # así la primera conexión de red se usa en componentes reales de CorePulse.
    progress("Instalando componentes de CorePulse…", 0.62)
    _install_runtime_lock()

    progress("Validando gráficos y sensores…", 0.88)
    ready, output = _verify_imports()
    if not ready:
        raise RuntimeError(
            "El entorno se instaló, pero la validación final no fue satisfactoria.\n\n"
            f"Detalle: {output[-700:] if output else 'sin detalle'}"
        )
    _write_marker(lock_hash)
    progress("CorePulse está listo.", 1.0)


def _launch() -> None:
    entry = str(os.environ.get("COREPULSE_BOOTSTRAP_ENTRYPOINT") or "").strip().lower()
    script = ROOT / ("main.py" if entry == "main" else "corepulse_launcher.py")
    pyw = VENV_PYW if VENV_PYW.is_file() else VENV_PY
    env = os.environ.copy()
    env["COREPULSE_BOOTSTRAPPED"] = "1"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    subprocess.Popen([str(pyw), str(script)], cwd=str(ROOT), env=env, creationflags=creationflags)


def _run_gui() -> int:
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title("CorePulse — preparando este PC")
    root.geometry("520x190")
    root.resizable(False, False)
    root.configure(bg="#071522")
    try:
        icon = ROOT / "assets" / "app_icon.ico"
        if icon.is_file():
            root.iconbitmap(str(icon))
    except Exception:
        pass

    title = tk.Label(root, text="CorePulse está preparando este PC", bg="#071522", fg="#f8fafc", font=("Segoe UI Semibold", 16))
    title.pack(anchor="w", padx=28, pady=(28, 6))
    subtitle = tk.Label(root, text="Esto ocurre automáticamente sólo cuando el entorno falta o necesita reparación.", bg="#071522", fg="#94a3b8", font=("Segoe UI", 9))
    subtitle.pack(anchor="w", padx=28)
    status_var = tk.StringVar(value="Comprobando…")
    status = tk.Label(root, textvariable=status_var, bg="#071522", fg="#38bdf8", font=("Segoe UI", 9))
    status.pack(anchor="w", padx=28, pady=(22, 8))
    bar = ttk.Progressbar(root, orient="horizontal", mode="determinate", maximum=100, length=464)
    bar.pack(padx=28)

    outcome = {"error": None}

    def progress(text: str, value: float) -> None:
        root.after(0, lambda: (status_var.set(text), bar.configure(value=max(0, min(100, value * 100)))))

    def worker() -> None:
        try:
            _prepare(progress)
        except Exception as exc:
            _log(traceback.format_exc())
            outcome["error"] = f"{exc}\n\nRegistro: {LOG}"
        finally:
            root.after(0, finish)

    def finish() -> None:
        err = outcome.get("error")
        if err:
            messagebox.showerror("CorePulse — no se pudo preparar el entorno", err, parent=root)
            root.destroy()
            return
        root.destroy()
        _launch()

    root.after(100, lambda: threading.Thread(target=worker, daemon=True, name="CorePulse-Bootstrap").start())
    root.mainloop()
    return 1 if outcome.get("error") else 0


def main() -> int:
    try:
        LOG.write_text(f"CorePulse runtime bootstrap - {time.strftime('%Y-%m-%d %H:%M:%S')}\n", encoding="utf-8")
    except Exception:
        pass
    try:
        return _run_gui()
    except Exception:
        _log(traceback.format_exc())
        # Último fallback para entornos donde Tk no pueda abrirse.
        try:
            _prepare(lambda text, value: _log(f"{value:.0%} {text}"))
            _launch()
            return 0
        except Exception as exc:
            _log(traceback.format_exc())
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, f"{exc}\n\nRegistro: {LOG}", "CorePulse — error de preparación", 0x10)
            except Exception:
                pass
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
