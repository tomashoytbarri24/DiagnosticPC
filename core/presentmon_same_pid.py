"""Realiza una captura independiente de PresentMon limitada al mismo proceso seleccionado por RTSS."""
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
# Código refactorizado: nombres estables y documentación en español.
import csv, math, os, subprocess, tempfile, threading, time
from collections import deque
from pathlib import Path
POLICY = 'INDEPENDENT_PRESENTMON_SAME_PID_CROSSCHECK_ONLY'

def _finite(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except Exception:
        return None

class PresentMonSamePIDCapture:
    """Clase responsable de `PresentMonSamePIDCapture` dentro de CorePulse. Conserva los contratos de integridad del módulo."""

    def __init__(self, project_root=None, window_seconds=3.0):
        self.root = Path(project_root or Path(__file__).resolve().parents[1])
        self.exe = self.root / 'tools' / 'presentmon' / 'PresentMon.exe'
        self.window_seconds = max(1.0, float(window_seconds))
        self._lock = threading.RLock()
        self._pid = None
        self._proc = None
        self._csv = None
        self._started = None
        self._last_error = None

    def _stop_locked(self):
        p = self._proc
        self._proc = None
        if p is not None and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=2)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        self._pid = None
        self._started = None

    def stop(self):
        with self._lock:
            self._stop_locked()

    def ensure_pid(self, pid):
        pid = int(pid) if pid else None
        with self._lock:
            if not pid:
                self._stop_locked()
                return False
            if self._pid == pid and self._proc is not None and (self._proc.poll() is None):
                return True
            self._stop_locked()
            if not self.exe.exists():
                self._last_error = 'PRESENTMON_EXE_MISSING'
                return False
            fd, path = tempfile.mkstemp(prefix=f'corepulse_pm_{pid}_', suffix='.csv')
            os.close(fd)
            self._csv = Path(path)
            cmd = [str(self.exe), '--process_id', str(pid), '--output_file', str(self._csv), '--no_console_stats', '--terminate_after_timed', str(max(2, int(self.window_seconds + 1)))]
            try:
                self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                self._pid = pid
                self._started = time.time()
                self._last_error = None
                return True
            except Exception as e:
                self._last_error = f'{type(e).__name__}: {e}'
                self._stop_locked()
                return False

    def read(self, pid):
        pid = int(pid) if pid else None
        if not pid:
            return self._empty('NO_TARGET_PID')
        self.ensure_pid(pid)
        with self._lock:
            path = self._csv
            started = self._started
            err = self._last_error
        if err:
            return self._empty(err, pid)
        if not path or not path.exists() or path.stat().st_size < 10:
            return self._empty('CAPTURE_WARMING_UP', pid, started)
        rows = []
        try:
            with path.open('r', encoding='utf-8-sig', errors='replace', newline='') as f:
                for row in csv.DictReader(f):
                    rp = row.get('ProcessID') or row.get('ProcessId') or row.get('process_id')
                    try:
                        if rp is not None and int(float(rp)) != pid:
                            continue
                    except Exception:
                        continue
                    ms = _finite(row.get('MsBetweenPresents') or row.get('msBetweenPresents'))
                    if ms and 0 < ms < 1000:
                        rows.append(ms)
        except Exception as e:
            return self._empty(f'CSV_READ_ERROR:{type(e).__name__}', pid, started)
        if len(rows) < 15:
            return self._empty('INSUFFICIENT_SAME_PID_SAMPLES', pid, started, len(rows))
        recent = rows[-240:]
        avg = sum(recent) / len(recent)
        fps = 1000.0 / avg if avg > 0 else None
        ordered = sorted(recent, reverse=True)
        n = max(1, int(len(ordered) * 0.01))
        low_ms = sum(ordered[:n]) / n
        return {'version': VERSION, 'policy': POLICY, 'quality': 'VALID', 'pid': pid, 'fps': round(fps, 3) if fps else None, 'frametime_ms': round(avg, 3), 'fps_1pct_low': round(1000.0 / low_ms, 3) if low_ms > 0 else None, 'sample_count': len(recent), 'same_pid_enforced': True, 'source': 'PresentMon ETW', 'started_at': started, 'error': None, 'synthetic': False, 'estimated': False, 'interpolated': False}

    @staticmethod
    def _empty(reason, pid=None, started=None, samples=0):
        return {'version': VERSION, 'policy': POLICY, 'quality': 'UNAVAILABLE', 'pid': pid, 'fps': None, 'frametime_ms': None, 'fps_1pct_low': None, 'sample_count': samples, 'same_pid_enforced': True, 'source': 'PresentMon ETW', 'started_at': started, 'error': reason, 'synthetic': False, 'estimated': False, 'interpolated': False}
