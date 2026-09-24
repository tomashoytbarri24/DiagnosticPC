"""Instrumentación liviana del arranque de CorePulse.

V0.10.2.81w registra etapas con ``perf_counter`` sin ejecutar consultas de
hardware. La persistencia se realiza fuera de la ruta crítica. La 64w además mide el gate visual, la primera muestra real y el momento
en que se libera la ventana principal.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import threading
import time

_LOCK = threading.RLock()
_T0 = time.perf_counter()
_STAGES: list[dict] = []


def startup_mark(stage: str, **meta) -> dict:
    entry = {
        "stage": str(stage),
        "elapsed_ms": round((time.perf_counter() - _T0) * 1000.0, 3),
        "thread": threading.current_thread().name,
    }
    if meta:
        entry["meta"] = {str(k): v for k, v in meta.items()}
    with _LOCK:
        _STAGES.append(entry)
    return dict(entry)


def startup_snapshot() -> dict:
    with _LOCK:
        stages = [dict(item) for item in _STAGES]
    by_stage = {item["stage"]: item["elapsed_ms"] for item in stages}
    return {
        "schema": "corepulse.startup.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "stages": stages,
        "stage_ms": by_stage,
        "first_frame_ms": by_stage.get("first_frame_idle"),
        "charts_ready_ms": by_stage.get("charts_ready"),
        "services_ready_ms": by_stage.get("services_ready"),
        "first_telemetry_acquired_ms": by_stage.get("first_telemetry_acquired"),
        "first_telemetry_ui_ready_ms": by_stage.get("first_telemetry_ui_ready"),
        "runtime_integrity_ms": by_stage.get("runtime_integrity_ready"),
        "startup_gate_visible_ms": by_stage.get("startup_gate_visible"),
        "startup_gate_complete_ms": by_stage.get("startup_gate_complete"),
        "main_window_revealed_ms": by_stage.get("main_window_revealed"),
    }


def persist_startup_metrics(path=None):
    """Guarda la medición fuera de la ruta crítica del primer frame."""
    try:
        if path is None:
            from core.runtime_paths import state_path
            path = state_path("startup_metrics.json")
        payload = startup_snapshot()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
    except Exception:
        return None


startup_mark("profiler_loaded")
