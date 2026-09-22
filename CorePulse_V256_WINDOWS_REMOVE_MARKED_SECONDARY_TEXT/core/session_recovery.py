"""Recuperación de sesión tras cierres no limpios de CorePulse.

Este módulo NO revierte tweaks persistentes elegidos por el usuario. Su trabajo es:
- detectar si la sesión anterior terminó sin pasar por el cierre normal;
- conservar evidencia local del incidente;
- exponer el estado para UI/diagnóstico;
- registrar recuperaciones seguras que otros subsistemas ya realizan (Game Boost,
  energía temporal, etc.).

El marcador vive en AppData y no contiene datos personales ni telemetría sensible.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict

import psutil

from core.runtime_paths import state_path, diagnostics_dir
from core.version import VERSION_LABEL

SESSION_FILE = state_path('active_session.json')
HISTORY_FILE = state_path('recovery_history.json')
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default):
    try:
        if path.is_file():
            value = json.loads(path.read_text(encoding='utf-8'))
            return value
    except Exception:
        pass
    return default


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def _same_process_alive(payload: Dict[str, Any]) -> bool:
    try:
        pid = int(payload.get('pid') or 0)
        expected = float(payload.get('process_create_time') or 0.0)
        if pid <= 0 or not psutil.pid_exists(pid):
            return False
        proc = psutil.Process(pid)
        actual = float(proc.create_time())
        if expected > 0 and abs(actual - expected) > 2.0:
            return False
        return proc.is_running()
    except Exception:
        return False


def _append_history(entry: Dict[str, Any]) -> None:
    rows = _read_json(HISTORY_FILE, [])
    if not isinstance(rows, list):
        rows = []
    rows.append(dict(entry))
    rows = rows[-40:]
    _write_json(HISTORY_FILE, rows)


class SessionRecoveryManager:
    """Autoridad del marcador de sesión de CorePulse."""

    def __init__(self, session_path: Path | None = None, history_path: Path | None = None, crash_dir: Path | None = None):
        self.session_path = Path(session_path) if session_path else SESSION_FILE
        self.history_path = Path(history_path) if history_path else HISTORY_FILE
        self.crash_dir = Path(crash_dir) if crash_dir else (Path(diagnostics_dir()) / 'crash_reports')
        self.current: Dict[str, Any] = {}
        self.previous_abnormal: Dict[str, Any] | None = None
        self.recovery_actions: list[dict] = []
        self.last_crash_report_path: str | None = None
        self._clean = False

    def _write_crash_report(self, abnormal: Dict[str, Any]) -> str | None:
        try:
            folder = self.crash_dir
            folder.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            path = folder / f'Crash_CorePulse_{stamp}.json'
            payload = {
                'schema': 'corepulse.crash_report.v1',
                'generated_at': _utc_now(),
                'abnormal_session': dict(abnormal),
                'recovery_actions': list(self.recovery_actions),
                'policy': 'LOCAL_TECHNICAL_METADATA_ONLY',
            }
            _write_json(path, payload)
            self.last_crash_report_path = str(path)
            return str(path)
        except Exception:
            return None

    def _refresh_crash_report_actions(self) -> None:
        path = Path(self.last_crash_report_path) if self.last_crash_report_path else None
        if path is None or not path.is_file():
            return
        try:
            payload = _read_json(path, {})
            if not isinstance(payload, dict):
                payload = {}
            payload['recovery_actions'] = list(self.recovery_actions)
            payload['updated_at'] = _utc_now()
            _write_json(path, payload)
        except Exception:
            pass

    def begin_session(self) -> Dict[str, Any]:
        with _LOCK:
            previous = _read_json(self.session_path, {})
            abnormal = None
            if isinstance(previous, dict) and previous.get('active'):
                # Si el PID anterior sigue siendo exactamente el mismo proceso,
                # no lo clasificamos como crash: puede existir una segunda instancia.
                if not _same_process_alive(previous):
                    abnormal = {
                        'detected': True,
                        'previous_version': previous.get('version'),
                        'previous_pid': previous.get('pid'),
                        'started_at': previous.get('started_at'),
                        'last_heartbeat_at': previous.get('last_heartbeat_at'),
                        'detected_at': _utc_now(),
                        'reason': 'La sesión anterior no alcanzó el cierre normal de CorePulse.',
                    }
                    self.previous_abnormal = abnormal
                    report_path = self._write_crash_report(abnormal)
                    if report_path:
                        abnormal['report_path'] = report_path
                        self.previous_abnormal = abnormal
                    # Usamos la ruta configurable del objeto para permitir pruebas.
                    old_history = _read_json(self.history_path, [])
                    if not isinstance(old_history, list):
                        old_history = []
                    old_history.append({'type': 'abnormal_shutdown', **abnormal})
                    _write_json(self.history_path, old_history[-40:])

            try:
                create_time = float(psutil.Process(os.getpid()).create_time())
            except Exception:
                create_time = time.time()
            self.current = {
                'schema': 'corepulse.session.v1',
                'active': True,
                'clean_shutdown': False,
                'version': VERSION_LABEL,
                'pid': os.getpid(),
                'process_create_time': create_time,
                'started_at': _utc_now(),
                'last_heartbeat_at': _utc_now(),
                'recovery_actions': [],
            }
            _write_json(self.session_path, self.current)
            self._clean = False
            return self.status()

    def heartbeat(self) -> None:
        with _LOCK:
            if not self.current or self._clean:
                return
            self.current['last_heartbeat_at'] = _utc_now()
            _write_json(self.session_path, self.current)

    def record_recovery_action(self, component: str, success: bool, message: str, **meta) -> Dict[str, Any]:
        entry = {
            'component': str(component or 'CorePulse'),
            'success': bool(success),
            'message': str(message or ''),
            'timestamp': _utc_now(),
        }
        if meta:
            entry['meta'] = {str(k): v for k, v in meta.items()}
        with _LOCK:
            self.recovery_actions.append(entry)
            if self.current and not self._clean:
                self.current['recovery_actions'] = list(self.recovery_actions[-20:])
                _write_json(self.session_path, self.current)
            self._refresh_crash_report_actions()
        return dict(entry)

    def mark_clean_shutdown(self) -> Dict[str, Any]:
        with _LOCK:
            if self._clean:
                return self.status()
            self._clean = True
            if self.current:
                self.current.update({
                    'active': False,
                    'clean_shutdown': True,
                    'closed_at': _utc_now(),
                    'last_heartbeat_at': _utc_now(),
                    'recovery_actions': list(self.recovery_actions[-20:]),
                })
                # Guardamos el cierre limpio en historial y retiramos el marcador
                # activo para que un arranque futuro no pueda confundirlo con crash.
                history = _read_json(self.history_path, [])
                if not isinstance(history, list):
                    history = []
                history.append({
                    'type': 'clean_shutdown',
                    'version': self.current.get('version'),
                    'started_at': self.current.get('started_at'),
                    'closed_at': self.current.get('closed_at'),
                })
                _write_json(self.history_path, history[-40:])
            try:
                self.session_path.unlink(missing_ok=True)
            except Exception:
                pass
            return self.status()

    def history(self, limit: int = 12) -> list[dict]:
        rows = _read_json(self.history_path, [])
        if not isinstance(rows, list):
            return []
        return [dict(x) for x in rows[-max(1, int(limit)):][::-1] if isinstance(x, dict)]

    def status(self) -> Dict[str, Any]:
        return {
            'previous_abnormal': dict(self.previous_abnormal) if isinstance(self.previous_abnormal, dict) else None,
            'current_active': bool(self.current and not self._clean),
            'current_version': self.current.get('version') if self.current else VERSION_LABEL,
            'recovery_actions': list(self.recovery_actions),
            'history': self.history(8),
            'crash_report_path': self.last_crash_report_path,
            'policy': 'DETECT_ABNORMAL_CLOSE_RESTORE_ONLY_TEMPORARY_STATE',
        }


__all__ = ['SessionRecoveryManager', 'SESSION_FILE', 'HISTORY_FILE']
