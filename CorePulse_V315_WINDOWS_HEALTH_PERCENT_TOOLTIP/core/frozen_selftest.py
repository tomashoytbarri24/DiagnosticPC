"""Self-test de integridad del ejecutable CorePulse.

Se ejecuta sin abrir la GUI y es usado por build_exe.bat. Un build sólo se marca
VALIDADO si todos los checks críticos del bundle pasan. Condiciones externas
(RTSS, API key, PawnIO, Ookla instalado, privilegios) son advertencias.
"""
from __future__ import annotations

from datetime import datetime, timezone
import ctypes
import importlib
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import traceback

from core.runtime_paths import (
    cache_dir, config_dir, data_dir, diagnostics_dir, executable_root, is_frozen,
    log_dir, resource_path, resource_root, state_dir,
)
from core.version import VERSION


def _item(name, critical, ok, detail=""):
    return {"name": name, "critical": bool(critical), "ok": bool(ok), "detail": str(detail or "")}


def _import_check(name, label=None):
    try:
        importlib.import_module(name)
        return _item(label or f"import:{name}", True, True, "OK")
    except Exception as exc:
        return _item(label or f"import:{name}", True, False, f"{type(exc).__name__}: {exc}")


def _is_admin():
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _find_rtss():
    if os.name != "nt":
        return None
    for path in (
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "RivaTuner Statistics Server" / "RTSS.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "RivaTuner Statistics Server" / "RTSS.exe",
    ):
        if path.is_file():
            return path
    return None


def _find_pawnio():
    if os.name != "nt":
        return None
    pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    pf86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    system = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    candidates = (
        pf / "PawnIO" / "PawnIO.exe",
        pf86 / "PawnIO" / "PawnIO.exe",
        system / "System32" / "drivers" / "PawnIO.sys",
    )
    for path in candidates:
        if path.is_file():
            return path
    # Consulta rápida del servicio/driver, sin recorrer Program Files completo.
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(["sc.exe", "query", "PawnIO"], capture_output=True, text=True, timeout=4, creationflags=flags)
        if proc.returncode == 0:
            return Path("PawnIO(service)")
    except Exception:
        pass
    return None


def _same_exe_probe(items):
    out = state_dir() / "selftest_helper_probe.json"
    out.unlink(missing_ok=True)
    if is_frozen():
        cmd = [str(sys.executable), "--corepulse-helper-probe", "--output", str(out)]
    else:
        launcher = resource_path("corepulse_launcher.py")
        cmd = [str(sys.executable), str(launcher), "--corepulse-helper-probe", "--output", str(out)]
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        proc = subprocess.run(cmd, timeout=30, creationflags=flags)
        payload = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
        ok = proc.returncode == 0 and payload.get("ok") is True and payload.get("version") == VERSION
        items.append(_item("same_exe_internal_cli", True, ok, f"returncode={proc.returncode}; output={out}"))
    except Exception as exc:
        items.append(_item("same_exe_internal_cli", True, False, f"{type(exc).__name__}: {exc}"))
    finally:
        out.unlink(missing_ok=True)


def run_self_test(output_path=None) -> tuple[int, dict]:
    items = []
    warnings = []

    items.append(_item("windows", True, platform.system() == "Windows", platform.platform()))
    items.append(_item("frozen_pyinstaller", True, is_frozen(), f"sys.frozen={getattr(sys, 'frozen', False)!r}"))
    items.append(_item("runtime_x64", True, struct.calcsize("P") * 8 == 64, f"{struct.calcsize('P')*8}-bit"))
    items.append(_item("python_runtime", True, sys.version_info[:2] == (3, 12), sys.version.split()[0]))

    # Separación recursos/estado: crítico para instalación y upgrades.
    try:
        rr = resource_root().resolve()
        ed = executable_root().resolve()
        dirs = [data_dir(), state_dir(), diagnostics_dir(), config_dir(), cache_dir(), log_dir()]
        writable = True
        detail = []
        for folder in dirs:
            probe = folder / ".corepulse_selftest_write"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            detail.append(str(folder))
        if is_frozen():
            # Ninguna carpeta mutable debe estar debajo de _internal/resource_root.
            for folder in dirs:
                try:
                    folder.resolve().relative_to(rr)
                    writable = False
                    detail.append(f"ERROR mutable dentro de bundle: {folder}")
                except ValueError:
                    pass
        items.append(_item("appdata_runtime_paths", True, writable, " | ".join(detail)))
    except Exception as exc:
        items.append(_item("appdata_runtime_paths", True, False, f"{type(exc).__name__}: {exc}"))

    required_resources = [
        ("app_icon", resource_path("assets", "app_icon.ico")),
        ("corepulse_icon", resource_path("assets", "CorePulseIcon.png")),
        ("presentmon", resource_path("tools", "presentmon", "PresentMon.exe")),
        ("speedtest_installer", resource_path("Instalar_Speedtest_Ookla.bat")),
    ]
    for name, path in required_resources:
        items.append(_item(f"resource:{name}", True, path.is_file(), str(path)))

    for mod in (
        "psutil", "customtkinter", "PIL", "matplotlib", "reportlab", "platformdirs",
        "send2trash", "groq", "dotenv", "pystray", "wmi", "win32api", "pythoncom",
        "pywintypes", "clr", "pythonnet", "clr_loader",
    ):
        items.append(_import_check(mod))

    # HardwareMonitor: el bug concreto de 41b/41c queda convertido en check crítico.
    try:
        import HardwareMonitor  # noqa: F401
        from HardwareMonitor.Hardware import Computer
        items.append(_item("hardwaremonitor_clr_namespace", True, True, "Computer importado"))
        try:
            c = Computer()
            items.append(_item("hardwaremonitor_computer_ctor", True, c is not None, "Computer() creado"))
            # Open() valida que las dependencias CLR se pueden resolver. Una falta de
            # permisos/PawnIO no invalida el bundle; FileNotFound/DllNotFound sí.
            try:
                c.IsCpuEnabled = True
                c.IsGpuEnabled = True
                c.IsMemoryEnabled = True
                c.IsStorageEnabled = True
                c.Open()
                count = len(list(c.Hardware))
                warnings.append({"name": "sensor_open", "ok": True, "detail": f"Hardware enumerado: {count}"})
            except Exception as exc:
                text = f"{type(exc).__name__}: {exc}"
                assembly_broken = any(x in text.lower() for x in ("filenotfound", "dllnotfound", "could not load file", "assembly"))
                if assembly_broken:
                    items.append(_item("hardwaremonitor_open_assemblies", True, False, text))
                else:
                    warnings.append({"name": "sensor_open", "ok": False, "detail": text})
            finally:
                try: c.Close()
                except Exception: pass
        except Exception as exc:
            items.append(_item("hardwaremonitor_computer_ctor", True, False, f"{type(exc).__name__}: {exc}"))
    except Exception as exc:
        items.append(_item("hardwaremonitor_clr_namespace", True, False, f"{type(exc).__name__}: {exc}"))

    # ReportLab real: no basta con importar el paquete.
    try:
        from reportlab.pdfgen import canvas
        pdf = diagnostics_dir() / "selftest_reportlab.pdf"
        c = canvas.Canvas(str(pdf)); c.drawString(20, 20, "CorePulse self-test"); c.save()
        ok = pdf.is_file() and pdf.stat().st_size > 100
        items.append(_item("reportlab_pdf_write", True, ok, str(pdf)))
        pdf.unlink(missing_ok=True)
    except Exception as exc:
        items.append(_item("reportlab_pdf_write", True, False, f"{type(exc).__name__}: {exc}"))

    try:
        db = diagnostics_dir() / "selftest.sqlite3"
        con = sqlite3.connect(db); con.execute("create table if not exists t(v integer)"); con.execute("insert into t values (1)"); con.commit()
        value = con.execute("select count(*) from t").fetchone()[0]; con.close(); db.unlink(missing_ok=True)
        items.append(_item("sqlite_write_read", True, value >= 1, f"rows={value}"))
    except Exception as exc:
        items.append(_item("sqlite_write_read", True, False, f"{type(exc).__name__}: {exc}"))

    # Importa el grafo principal sin instanciar Tk. Detecta imports dinámicos faltantes.
    try:
        import main  # noqa: F401
        items.append(_item("main_module_graph", True, True, "main importado sin crear App"))
    except Exception as exc:
        items.append(_item("main_module_graph", True, False, f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}"))

    _same_exe_probe(items)

    # Condiciones externas: informativas, no pueden falsearse ni empaquetarse.
    warnings.extend([
        {"name": "admin", "ok": _is_admin(), "detail": "Algunas acciones elevan UAC sólo cuando corresponde"},
        {"name": "rtss", "ok": _find_rtss() is not None, "detail": str(_find_rtss() or "No detectado; overlay/FPS puede usar PresentMon o quedar N/A")},
        {"name": "ookla_cli", "ok": bool(shutil.which("speedtest.exe") or shutil.which("speedtest")), "detail": "Instalable desde Red avanzada"},
        {"name": "groq_key", "ok": bool(str(os.environ.get("GROQ_API_KEY") or "").strip()), "detail": "La IA es opcional; diagnóstico determinístico no depende de la clave"},
        {"name": "pawnio", "ok": _find_pawnio() is not None, "detail": str(_find_pawnio() or "No detectado; algunos sensores de placa pueden quedar N/A")},
    ])

    failed = [x for x in items if x["critical"] and not x["ok"]]
    report = {
        "schema": 1,
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready": not failed,
        "critical_total": sum(1 for x in items if x["critical"]),
        "critical_failed": len(failed),
        "items": items,
        "warnings": warnings,
        "resource_root": str(resource_root()),
        "executable_root": str(executable_root()),
    }
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return (0 if report["ready"] else 10), report
