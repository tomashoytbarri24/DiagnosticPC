"""Preflight de arranque de CorePulse.

El preflight de usuario NO sustituye al self-test de build. En una instalación
final permite abrir CorePulse aunque una capacidad externa no esté disponible,
pero registra con precisión qué subsistema queda N/A.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import ctypes
import importlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import struct
import sys

from core.runtime_paths import (
    executable_root, is_frozen, resource_path, state_path, state_dir,
)

ESSENTIAL_IMPORTS = (
    ("psutil", "psutil"),
    ("customtkinter", "CustomTkinter"),
    ("PIL", "Pillow"),
    ("matplotlib", "Matplotlib"),
    ("platformdirs", "platformdirs"),
)

BUNDLED_CAPABILITY_IMPORTS = (
    ("reportlab", "Generación PDF"),
    ("send2trash", "Send2Trash"),
    ("groq", "SDK Groq"),
    ("dotenv", "python-dotenv"),
    ("pystray", "Icono de bandeja"),
)

WINDOWS_CAPABILITY_IMPORTS = (
    ("wmi", "WMI"),
    ("win32api", "pywin32"),
    ("clr", "pythonnet"),
)


@dataclass(frozen=True)
class ReadinessItem:
    id: str
    label: str
    status: str
    required: bool
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "OK"


@dataclass
class ReadinessReport:
    generated_at: str
    version: str
    platform: str
    python: str
    architecture: str
    ready: bool
    frozen: bool
    items: list[ReadinessItem]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["errors"] = [asdict(i) for i in self.items if i.required and not i.ok]
        data["warnings"] = [asdict(i) for i in self.items if not i.required and not i.ok]
        return data


def _module_check(name: str) -> tuple[bool, str]:
    try:
        if is_frozen():
            importlib.import_module(name)
            return True, "incluido y cargable desde CorePulse.exe"
        spec = importlib.util.find_spec(name)
        return bool(spec), f"módulo {name}" if spec else f"módulo {name} no instalado"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _platform_check() -> tuple[bool, str]:
    system = platform.system()
    if system == "Windows":
        try:
            ver = sys.getwindowsversion()
            return int(ver.major) >= 10, f"Windows {ver.major}.{ver.minor} build {ver.build}"
        except Exception:
            return True, platform.platform()
    if system == "Linux":
        return True, platform.platform()
    return False, f"{system} todavía no es plataforma objetivo"

def _is_admin() -> bool:
    if platform.system() == "Windows":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    if platform.system() == "Linux":
        try:
            return os.geteuid() == 0
        except Exception:
            return False
    return False

def _find_rtss() -> str | None:
    if platform.system() != "Windows":
        return None
    for path in (
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "RivaTuner Statistics Server" / "RTSS.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "RivaTuner Statistics Server" / "RTSS.exe",
    ):
        if path.is_file():
            return str(path)
    return None


def _find_speedtest() -> str | None:
    found = shutil.which("speedtest.exe") or shutil.which("speedtest")
    if found:
        return found
    for path in (
        resource_path("tools", "speedtest.exe"),
        resource_path("tools", "ookla", "speedtest.exe"),
        executable_root() / "speedtest.exe",
    ):
        if path.is_file():
            return str(path)
    return None


def _probe_hardwaremonitor() -> tuple[bool, str]:
    """Sondea HardwareMonitor sin permitir que pythonnet bloquee el arranque.

    En modo fuente el import se ejecuta en un proceso hijo con timeout. Algunas
    combinaciones de pythonnet/LHM pueden quedar esperando indefinidamente al
    inicializar CLR aunque no exista una excepción visible en la terminal.
    HardwareMonitor es una capacidad opcional: un timeout se reporta como N/A y
    nunca debe secuestrar la pantalla de preparación de CorePulse.
    """
    if not is_frozen():
        code = (
            "import HardwareMonitor; "
            "from HardwareMonitor.Hardware import Computer; "
            "print('COREPULSE_HM_OK')"
        )
        try:
            cp = subprocess.run(
                [sys.executable, '-c', code],
                capture_output=True,
                text=True,
                errors='replace',
                timeout=5,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            if cp.returncode == 0 and 'COREPULSE_HM_OK' in (cp.stdout or ''):
                return True, "HardwareMonitor + LibreHardwareMonitorLib cargados"
            detail = (cp.stderr or cp.stdout or '').strip()
            return False, detail[-500:] if detail else f"proceso de comprobación terminó con código {cp.returncode}"
        except subprocess.TimeoutExpired:
            return False, "TIMEOUT: HardwareMonitor no respondió en 5 s; sensores profundos quedan N/A"
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"
    try:
        import HardwareMonitor  # noqa: F401
        from HardwareMonitor.Hardware import Computer  # noqa: F401
        return True, "HardwareMonitor + LibreHardwareMonitorLib cargados"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def collect_readiness(project_root=None, version: str = "unknown") -> ReadinessReport:
    items: list[ReadinessItem] = []
    platform_ok, platform_detail = _platform_check()
    system = platform.system()
    label = "Windows 10/11 x64" if system == "Windows" else "Linux x64" if system == "Linux" else system
    items.append(ReadinessItem("platform", label, "OK" if platform_ok else "ERROR", True, platform_detail))

    py_ok = sys.version_info >= (3, 12)
    items.append(ReadinessItem(
        "python", "Runtime Python 3.12+", "OK" if py_ok else "ERROR", True,
        ("runtime integrado " if is_frozen() else "") + sys.version.split()[0],
    ))
    bits = struct.calcsize("P") * 8
    items.append(ReadinessItem("runtime_x64", "Runtime x64", "OK" if bits == 64 else "ERROR", True, f"{bits}-bit"))

    for module, label in ESSENTIAL_IMPORTS:
        ok, detail = _module_check(module)
        items.append(ReadinessItem(f"import_{module}", label, "OK" if ok else "ERROR", True, detail))

    for module, label in BUNDLED_CAPABILITY_IMPORTS:
        ok, detail = _module_check(module)
        items.append(ReadinessItem(f"import_{module}", label, "OK" if ok else "N/A", False, detail))

    if platform.system() == "Windows":
        for module, label in WINDOWS_CAPABILITY_IMPORTS:
            ok, detail = _module_check(module)
            items.append(ReadinessItem(f"import_{module}", label, "OK" if ok else "N/A", False, detail))
        hm_ok, hm_detail = _probe_hardwaremonitor()
        items.append(ReadinessItem("hardwaremonitor", "LibreHardwareMonitor", "OK" if hm_ok else "N/A", False, hm_detail))

    elif platform.system() == "Linux":
        items.append(ReadinessItem(
            "linux_sensors", "Sensores Linux nativos", "OK", False,
            "psutil + sysfs; NVIDIA usa nvidia-smi si está disponible",
        ))
        for tool, label in (("smartctl", "smartmontools / SMART"), ("nvidia-smi", "NVIDIA SMI"),
                            ("aplay", "ALSA playback"), ("arecord", "ALSA capture"),
                            ("xdg-open", "xdg-open"), ("git", "Git")):
            found = shutil.which(tool)
            items.append(ReadinessItem(f"tool_{tool}", label, "OK" if found else "N/A", False,
                                       found or f"{tool} no instalado"))

    try:
        folder = state_dir()
        probe = folder / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        writable, writable_detail = True, str(folder)
    except Exception as exc:
        writable, writable_detail = False, f"{type(exc).__name__}: {exc}"
    items.append(ReadinessItem("runtime_dir", "Estado de usuario escribible", "OK" if writable else "ERROR", True, writable_detail))

    if platform.system() == "Windows":
        pm = resource_path("tools", "presentmon", "PresentMon.exe")
        items.append(ReadinessItem("presentmon", "PresentMon", "OK" if pm.is_file() else "N/A", False, str(pm)))

    speedtest = _find_speedtest()
    items.append(ReadinessItem("speedtest", "Ookla Speedtest CLI", "OK" if speedtest else "N/A", False, speedtest or "No instalado; se puede instalar desde Red avanzada"))

    if platform.system() == "Windows":
        rtss = _find_rtss()
        items.append(ReadinessItem("rtss", "RTSS para Overlay/FPS", "OK" if rtss else "N/A", False, rtss or "No detectado; FPS queda REAL_FPS_OR_NA_ONLY"))

    groq_key = bool(str(os.environ.get("GROQ_API_KEY") or "").strip())
    items.append(ReadinessItem("groq_key", "IA Groq configurada", "OK" if groq_key else "N/A", False, "GROQ_API_KEY configurada" if groq_key else "Sin API key; diagnóstico determinístico sigue disponible"))
    privilege_label = "Administrador" if platform.system() == "Windows" else "root"
    privilege_detail = ("No es obligatorio; CorePulse eleva sólo acciones que lo necesitan"
                        if platform.system() == "Windows" else
                        "No es obligatorio; CorePulse no ejecuta sudo automáticamente")
    items.append(ReadinessItem("admin", privilege_label, "OK" if _is_admin() else "INFO", False, privilege_detail))

    ready = all(item.ok for item in items if item.required)
    return ReadinessReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        version=str(version), platform=platform.platform(), python=sys.version.split()[0],
        architecture=f"{bits}-bit", ready=ready, frozen=is_frozen(), items=items,
    )



def collect_launch_gate(version: str = "unknown") -> ReadinessReport:
    """Gate mínimo para publicar la ventana lo antes posible.

    No importa Matplotlib, WMI, pythonnet, LHM, Groq, RTSS ni otras
    capacidades opcionales. La auditoría completa continúa en background.
    """
    items: list[ReadinessItem] = []
    platform_ok, platform_detail = _platform_check()
    system = platform.system()
    label = "Windows 10/11 x64" if system == "Windows" else "Linux x64" if system == "Linux" else system
    items.append(ReadinessItem("platform", label, "OK" if platform_ok else "ERROR", True, platform_detail))
    py_ok = sys.version_info >= (3, 12)
    items.append(ReadinessItem("python", "Runtime Python 3.12+", "OK" if py_ok else "ERROR", True, sys.version.split()[0]))
    bits = struct.calcsize("P") * 8
    items.append(ReadinessItem("runtime_x64", "Runtime x64", "OK" if bits == 64 else "ERROR", True, f"{bits}-bit"))
    ready = all(item.ok for item in items if item.required)
    return ReadinessReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        version=str(version), platform=platform.platform(), python=sys.version.split()[0],
        architecture=f"{bits}-bit", ready=ready, frozen=is_frozen(), items=items,
    )

def persist_readiness(report: ReadinessReport) -> Path | None:
    try:
        path = state_path("startup_readiness.json")
        path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path
    except Exception:
        return None


def update_first_run_state(version: str) -> tuple[bool, Path | None]:
    try:
        path = state_path("first_run_state.json")
        now = datetime.now(timezone.utc).isoformat()
        previous = {}
        if path.is_file():
            try:
                previous = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                previous = {}
        first = str(previous.get("last_version") or "") != str(version)
        path.write_text(json.dumps({
            "first_launch_at": previous.get("first_launch_at") or now,
            "last_launch_at": now,
            "last_version": str(version),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return first, path
    except Exception:
        return False, None


def format_blocking_message(report: ReadinessReport) -> str:
    failed = [i for i in report.items if i.required and not i.ok]
    lines = ["CorePulse no puede iniciar porque el núcleo de ejecución está incompleto.", ""]
    for item in failed[:12]:
        lines.append(f"• {item.label} — {item.detail}" if item.detail else f"• {item.label}")
    lines.append("")
    if report.frozen:
        lines.extend([
            "CorePulse.exe es autocontenido: no instales paquetes Python manualmente.",
            "Reinstala CorePulse o usa una compilación que haya superado el self-test de build.",
        ])
    else:
        lines.append("Instala las dependencias indicadas para tu plataforma y vuelve a abrir CorePulse.")
    return "\n".join(lines)
