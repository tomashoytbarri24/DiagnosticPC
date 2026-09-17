"""Prepara resolución de DLL CLR antes de importar HardwareMonitor."""
from pathlib import Path
import os
import sys

_handles = []
try:
    root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()
    candidates = [root / "HardwareMonitor" / "lib"]
    candidates += [p.parent for p in root.rglob("LibreHardwareMonitorLib.dll")]
    seen = set()
    for base in candidates:
        try: key = str(base.resolve()).casefold()
        except Exception: key = str(base).casefold()
        if key in seen or not base.exists():
            continue
        seen.add(key)
        os.environ["PATH"] = str(base) + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            try: _handles.append(os.add_dll_directory(str(base)))
            except Exception: pass
    # Mantener handles vivos durante toda la ejecución.
    sys._corepulse_dll_dir_handles = _handles
except Exception:
    pass
