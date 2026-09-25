"""Adquisición universal y trazable de frecuencia CPU para Windows/CorePulse.

Política: REAL_OR_NA. No inventa clocks, no aplica offsets y no rellena valores.
Prioridad:
1) el caller puede conservar los clocks por núcleo de LibreHardwareMonitor;
2) psutil.cpu_freq().current;
3) contadores CIM de Windows (ProcessorFrequency y PercentProcessorPerformance);
4) Win32_Processor.CurrentClockSpeed.

Los fallbacks 3/4 sólo se consultan cuando psutil no entrega una lectura válida.
"""
from __future__ import annotations

import json
import math
import os
import platform
import subprocess
import threading
import time

import psutil

_CACHE_LOCK = threading.RLock()
_CACHE = {"at": 0.0, "value": None}
_CACHE_SECONDS = 1.0


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if not math.isfinite(number):
        return None
    return number


def _valid_mhz(value):
    value = _num(value)
    if value is None or not (50.0 <= value <= 20000.0):
        return None
    return value


def _evidence(mhz, source, sensor, *, derived=False, detail=None):
    mhz = _valid_mhz(mhz)
    if mhz is None:
        return None
    return {
        "ghz": round(mhz / 1000.0, 3),
        "mhz": round(mhz, 3),
        "source": source,
        "sensor": sensor,
        "timestamp": time.time(),
        "quality": "VALID",
        "derived_from_real": bool(derived),
        "synthetic_adjustment": False,
        "interpolation": False,
        "offset_applied": 0.0,
        "detail": detail,
    }


def _from_psutil():
    try:
        freq = psutil.cpu_freq()
    except Exception:
        return None
    current = _valid_mhz(getattr(freq, "current", None) if freq else None)
    if current is None:
        return None
    return _evidence(
        current,
        "psutil.cpu_freq",
        "psutil.cpu_freq().current",
        detail="Frecuencia actual reportada por psutil/Windows",
    )


def _powershell_json(script, timeout=5):
    if os.name != "nt" and platform.system() != "Windows":
        return None
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    cmd = [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-Command", "$ProgressPreference='SilentlyContinue'; " + script + " | ConvertTo-Json -Depth 5 -Compress",
    ]
    try:
        cp = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=flags,
        )
        if cp.returncode != 0 or not cp.stdout.strip():
            return None
        return json.loads(cp.stdout.strip())
    except Exception:
        return None


def _as_rows(value):
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _from_windows_perf_cim():
    data = _powershell_json(
        "Get-CimInstance Win32_PerfFormattedData_Counters_ProcessorInformation -ErrorAction Stop "
        "| Where-Object { $_.Name -eq '_Total' } "
        "| Select-Object -First 1 Name,ProcessorFrequency,PercentProcessorPerformance"
    )
    rows = _as_rows(data)
    if not rows:
        return None
    row = rows[0]
    base = _valid_mhz(row.get("ProcessorFrequency"))
    perf = _num(row.get("PercentProcessorPerformance"))
    if base is not None and perf is not None and 1.0 <= perf <= 1000.0:
        effective = base * perf / 100.0
        if _valid_mhz(effective) is not None:
            return _evidence(
                effective,
                "Win32_PerfFormattedData_Counters_ProcessorInformation",
                "_Total / ProcessorFrequency × PercentProcessorPerformance / 100",
                derived=True,
                detail=f"ProcessorFrequency={base:.0f} MHz; PercentProcessorPerformance={perf:.1f}%",
            )
    if base is not None:
        return _evidence(
            base,
            "Win32_PerfFormattedData_Counters_ProcessorInformation",
            "_Total / ProcessorFrequency",
            detail="Frecuencia reportada por contador CIM de Windows",
        )
    return None


def _from_win32_processor():
    data = _powershell_json(
        "Get-CimInstance Win32_Processor -ErrorAction Stop "
        "| Select-Object Name,CurrentClockSpeed"
    )
    rows = _as_rows(data)
    values = [_valid_mhz(row.get("CurrentClockSpeed")) for row in rows]
    values = [v for v in values if v is not None]
    if not values:
        return None
    mhz = sum(values) / len(values)
    return _evidence(
        mhz,
        "Win32_Processor.CurrentClockSpeed",
        "Win32_Processor / CurrentClockSpeed",
        derived=len(values) > 1,
        detail="Frecuencia actual reportada por CIM de Windows",
    )


def get_cpu_frequency_evidence(force=False):
    """Devuelve evidencia real de frecuencia CPU o None.

    La lectura psutil se intenta siempre porque es barata y refleja el estado actual.
    Las consultas CIM se cachean brevemente para no lanzar PowerShell cada frame.
    """
    ps = _from_psutil()
    if ps is not None:
        return ps

    now = time.monotonic()
    with _CACHE_LOCK:
        if not force and _CACHE["value"] is not None and now - _CACHE["at"] <= _CACHE_SECONDS:
            return dict(_CACHE["value"])

    value = _from_windows_perf_cim() or _from_win32_processor()
    with _CACHE_LOCK:
        _CACHE["at"] = now
        _CACHE["value"] = dict(value) if isinstance(value, dict) else None
    return value
