"""Autodiagnóstico de capacidades de CorePulse.

V134 combina dos fuentes que CorePulse ya conoce:
- el preflight/runtime real del equipo actual;
- el último snapshot certificado de telemetría/sensores.

No genera puntuaciones de salud ni supone que una capacidad opcional ausente sea
un fallo. Los estados son descriptivos: AVAILABLE, PARTIAL, N/A, INFO o ERROR.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from typing import Any, Dict, Iterable, List

from core.runtime_paths import diagnostics_dir
from core.sensor_diagnostics import build_sensor_diagnostics
from core.startup_readiness import collect_readiness
from core.version import VERSION_LABEL

POLICY = "REAL_OR_NA_ONLY"
SCHEMA = 1


def _state_from_readiness(status: str, required: bool) -> str:
    raw = str(status or "N/A").upper()
    if raw == "OK":
        return "AVAILABLE"
    if raw == "INFO":
        return "INFO"
    if required:
        return "ERROR"
    return "N/A"


def _powershell_path() -> str | None:
    for name in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
        found = shutil.which(name)
        if found:
            return str(found)
    if os.name == "nt":
        root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        candidate = root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def _sensor_state(group: Dict[str, Any]) -> str:
    raw = str(group.get("state") or "UNAVAILABLE").upper()
    return {
        "AVAILABLE": "AVAILABLE",
        "PARTIAL": "PARTIAL",
        "UNAVAILABLE": "N/A",
    }.get(raw, "N/A")


def _sensor_detail(group: Dict[str, Any]) -> str:
    available = int(group.get("available") or 0)
    total = int(group.get("total") or 0)
    base = str(group.get("detail") or "").strip()
    sources = [str(x) for x in (group.get("sources") or []) if str(x).strip()]
    parts = [f"{available} de {total} lecturas certificadas"]
    if base:
        parts.append(base)
    if sources:
        parts.append("Fuentes: " + ", ".join(sources[:3]))
    return " · ".join(parts)


def _count_states(items: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"AVAILABLE": 0, "PARTIAL": 0, "N/A": 0, "INFO": 0, "ERROR": 0}
    for item in items:
        state = str(item.get("state") or "N/A").upper()
        if state not in counts:
            state = "N/A"
        counts[state] += 1
    return counts


def collect_corepulse_diagnostics(
    telemetry: Any = None,
    *,
    runtime_context: Dict[str, Any] | None = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """Construye un informe de capacidades sin convertir N/A en fallo.

    ``runtime_context`` puede incluir hechos ya conocidos por la UI (por ejemplo,
    si el agente está ejecutándose). No se infieren valores ausentes.
    """
    context = runtime_context if isinstance(runtime_context, dict) else {}
    readiness = collect_readiness(version=VERSION_LABEL)
    sensor_report = build_sensor_diagnostics(telemetry if isinstance(telemetry, dict) else {})

    runtime_items: List[Dict[str, Any]] = []
    optional_items: List[Dict[str, Any]] = []
    for item in readiness.items:
        row = {
            "id": str(item.id),
            "label": str(item.label),
            "state": _state_from_readiness(item.status, bool(item.required)),
            "required": bool(item.required),
            "detail": str(item.detail or ""),
            "source": "startup_readiness",
        }
        (runtime_items if item.required else optional_items).append(row)

    # PowerShell es necesario para DISM/SFC, pero no para el monitoreo normal.
    powershell = _powershell_path()
    optional_items.append({
        "id": "powershell",
        "label": "Windows PowerShell",
        "state": "AVAILABLE" if powershell else "N/A",
        "required": False,
        "detail": powershell or "No se detectó PowerShell; reparación DISM/SFC queda no disponible.",
        "source": "filesystem/path",
    })

    # Hechos del runtime que la propia App ya conoce; no se ejecutan probes nuevos.
    if "agent_running" in context:
        running = bool(context.get("agent_running"))
        optional_items.append({
            "id": "realtime_agent",
            "label": "Agente de monitoreo",
            "state": "AVAILABLE" if running else "INFO",
            "required": False,
            "detail": "Agente en ejecución" if running else "El agente todavía no reporta ejecución activa.",
            "source": "runtime_context",
        })
    if "telemetry_snapshot" in context:
        has_snapshot = bool(context.get("telemetry_snapshot"))
        optional_items.append({
            "id": "telemetry_snapshot",
            "label": "Snapshot de telemetría",
            "state": "AVAILABLE" if has_snapshot else "INFO",
            "required": False,
            "detail": "Existe un snapshot real disponible" if has_snapshot else "Aún no se recibió un snapshot de telemetría.",
            "source": "runtime_context",
        })

    sensor_items: List[Dict[str, Any]] = []
    for group in sensor_report.get("groups") or []:
        if not isinstance(group, dict):
            continue
        sensor_items.append({
            "id": "sensor_" + str(group.get("key") or "unknown"),
            "label": str(group.get("label") or "Sensores"),
            "state": _sensor_state(group),
            "required": False,
            "detail": _sensor_detail(group),
            "source": "CURRENT_TELEMETRY_SNAPSHOT",
            "metrics": list(group.get("metrics") or []),
            "unavailable": list(group.get("unavailable") or []),
        })

    all_items = runtime_items + optional_items + sensor_items
    counts = _count_states(all_items)
    critical_errors = [x for x in runtime_items if x.get("state") == "ERROR"]
    if critical_errors:
        overall = "ERROR"
        title = "El núcleo de CorePulse requiere atención"
    else:
        overall = "AVAILABLE"
        title = "Núcleo de CorePulse listo"

    report: Dict[str, Any] = {
        "schema": SCHEMA,
        "version": VERSION_LABEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": POLICY,
        "overall_state": overall,
        "title": title,
        "ready": not critical_errors,
        "counts": counts,
        "runtime": runtime_items,
        "optional": optional_items,
        "sensors": sensor_items,
        "sensor_metrics_available": int(sensor_report.get("available") or 0),
        "sensor_metrics_total": int(sensor_report.get("total") or 0),
        "note": "N/A significa que la capacidad no está instalada, presente o expuesta; no se interpreta como fallo del equipo.",
    }

    if persist:
        try:
            path = diagnostics_dir() / "corepulse_capabilities.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            report["report_path"] = str(path)
        except Exception as exc:
            report["persist_error"] = f"{type(exc).__name__}: {exc}"
    return report
