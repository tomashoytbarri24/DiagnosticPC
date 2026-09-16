# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller ONEDIR de CorePulse V0.10.2.81w.

El build incluye todas las dependencias que pertenecen al producto. Sólo quedan
externos los componentes que por diseño son instalaciones/servicios del sistema
(RTSS, PawnIO, Ookla CLI y credenciales de IA).
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent

datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "tools"), "tools"),
    (str(ROOT / ".env.example"), "."),
    (str(ROOT / "Instalar_Speedtest_Ookla.bat"), "."),
]
binaries = []
hiddenimports = [
    "HardwareMonitor",
    "clr", "pythonnet", "clr_loader",
    "wmi", "win32api", "win32com", "pythoncom", "pywintypes",
    "send2trash", "send2trash.win", "send2trash.win.modern", "send2trash.win.legacy",
    "groq", "dotenv", "pystray", "pystray._win32",
]

# Paquetes con imports dinámicos habituales.
for package in ("wmi", "win32com", "pystray", "groq", "dotenv", "send2trash"):
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

# HardwareMonitor instala LibreHardwareMonitorLib.dll y sus dependencias como
# package-data bajo HardwareMonitor/lib. Esto es CRÍTICO para temperaturas/GPU.
for package in ("HardwareMonitor", "pythonnet", "clr_loader", "customtkinter"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception as exc:
        print(f"[CorePulse.spec] ERROR recolectando {package}: {exc}")

# Algunos SDK consultan su metadata en tiempo de ejecución.
for package in ("groq", "pythonnet", "HardwareMonitor"):
    try:
        datas += copy_metadata(package)
    except Exception:
        pass

hiddenimports = sorted(set(hiddenimports))

a = Analysis(
    [str(ROOT / "corepulse_launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "build" / "runtime_hooks" / "corepulse_frozen_runtime.py")],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CorePulse",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "assets" / "app_icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CorePulse",
)
