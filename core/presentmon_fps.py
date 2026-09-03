"""Obtiene FPS reales por proceso mediante PresentMon y ETW."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import csv
import ctypes
import os
import shutil
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
import psutil
IS_WINDOWS = os.name == 'nt'
COREPULSE_SESSION = 'CorePulsePresentMon'

class PresentMonFPS:

    def __init__(self, project_root=None):
        self.project_root = Path(project_root or Path(__file__).resolve().parents[1])
        self._lock = threading.RLock()
        self._running = True
        self._process = None
        self._reader_thread = None
        self._target_pid = None
        self._target_name = None
        self._target_title = None
        self._fps = None
        self._frametime_ms = None
        self._fps_1pct_low = None
        self._sample_count = 0
        self._quality = 'UNAVAILABLE'
        self._error = None
        self._frame_times = deque(maxlen=240)
        self._presentmon = self._find_presentmon()
        self._cleanup_corepulse_session()
        self._manager_thread = threading.Thread(target=self._manager_loop, daemon=True, name='CorePulse-PresentMon-Manager')
        self._manager_thread.start()

    @property
    def executable(self):
        return str(self._presentmon) if self._presentmon else None

    def _find_presentmon(self):
        candidates = [self.project_root / 'tools' / 'presentmon' / 'PresentMon.exe', self.project_root / 'tools' / 'PresentMon.exe', self.project_root / 'PresentMon.exe']
        for candidate in candidates:
            if candidate.exists():
                return candidate
        found = shutil.which('PresentMon.exe') or shutil.which('PresentMon')
        return Path(found) if found else None

    def _cleanup_corepulse_session(self):
        if self._presentmon is None:
            return
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if IS_WINDOWS else 0
        try:
            subprocess.run([str(self._presentmon), '--session_name', COREPULSE_SESSION, '--terminate_existing_session'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, creationflags=creationflags)
        except Exception:
            pass

    @staticmethod
    def _foreground_window():
        if not IS_WINDOWS:
            return (None, None)
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return (None, None)
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            return (int(pid.value), buffer.value.strip())
        except Exception:
            return (None, None)

    def _is_capture_candidate(self, pid):
        if not pid or pid <= 4 or pid == os.getpid():
            return False
        try:
            name = (psutil.Process(pid).name() or '').lower()
        except Exception:
            return False
        blocked = {'explorer.exe', 'dwm.exe', 'applicationframehost.exe', 'searchhost.exe', 'startmenuexperiencehost.exe', 'shellexperiencehost.exe', 'textinputhost.exe', 'taskmgr.exe', 'code.exe', 'python.exe', 'pythonw.exe', 'powershell.exe', 'pwsh.exe', 'cmd.exe'}
        return name not in blocked

    def _manager_loop(self):
        while self._running:
            try:
                pid, title = self._foreground_window()
                if pid and self._is_capture_candidate(pid):
                    if pid != self._target_pid:
                        self._switch_target(pid, title)
            except Exception as exc:
                with self._lock:
                    self._error = str(exc)
            time.sleep(0.75)

    def _switch_target(self, pid, title=None):
        try:
            proc = psutil.Process(pid)
            name = proc.name()
        except Exception:
            return
        self._stop_capture()
        with self._lock:
            self._target_pid = int(pid)
            self._target_name = name
            self._target_title = title or name
            self._fps = None
            self._frametime_ms = None
            self._fps_1pct_low = None
            self._sample_count = 0
            self._frame_times.clear()
            self._quality = 'STARTING'
            self._error = None
        if self._presentmon is None:
            with self._lock:
                self._quality = 'UNAVAILABLE'
                self._error = 'PresentMon.exe no encontrado. Colócalo en tools/presentmon/PresentMon.exe.'
            return
        self._start_capture(pid)

    def _start_capture(self, pid):
        command = [str(self._presentmon), '--session_name', COREPULSE_SESSION, '--stop_existing_session', '--process_id', str(pid), '--output_stdout', '--v2_metrics', '--no_console_stats', '--exclude_dropped', '--terminate_on_proc_exit']
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if IS_WINDOWS else 0
        try:
            self._process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', bufsize=1, creationflags=creationflags)
            self._reader_thread = threading.Thread(target=self._reader_loop, args=(self._process,), daemon=True, name='CorePulse-PresentMon-Reader')
            self._reader_thread.start()
        except Exception as exc:
            with self._lock:
                self._quality = 'ERROR'
                self._error = f'No se pudo iniciar PresentMon: {exc}'

    @staticmethod
    def _parse_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _reader_loop(self, process):
        if process.stdout is None:
            return
        header = None
        try:
            for raw_line in process.stdout:
                if not self._running or process is not self._process:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                if header is None:
                    if 'Application' not in line or ',' not in line:
                        continue
                    header = next(csv.reader([line]))
                    continue
                try:
                    values = next(csv.reader([line]))
                except Exception:
                    continue
                if len(values) != len(header):
                    continue
                row = dict(zip(header, values))
                frame_time = None
                for key in ('FrameTime', 'MsBetweenPresents', 'msBetweenPresents'):
                    if key in row:
                        frame_time = self._parse_float(row.get(key))
                        if frame_time is not None:
                            break
                if frame_time is None or frame_time <= 0 or frame_time > 1000:
                    continue
                fps = 1000.0 / frame_time
                if fps <= 0 or fps > 2000:
                    continue
                with self._lock:
                    self._frame_times.append(frame_time)
                    self._sample_count += 1
                    self._fps = fps
                    self._frametime_ms = frame_time
                    self._quality = 'VALID'
                    self._error = None
                    if len(self._frame_times) >= 30:
                        sorted_times = sorted(self._frame_times, reverse=True)
                        count = max(1, int(len(sorted_times) * 0.01))
                        slowest = sorted_times[:count]
                        avg_slowest = sum(slowest) / len(slowest)
                        self._fps_1pct_low = 1000.0 / avg_slowest if avg_slowest > 0 else None
        except Exception as exc:
            with self._lock:
                self._quality = 'ERROR'
                self._error = f'Error leyendo PresentMon: {exc}'
        finally:
            if process is self._process and self._running:
                stderr_text = ''
                try:
                    if process.stderr:
                        stderr_text = process.stderr.read().strip()
                except Exception:
                    pass
                with self._lock:
                    if self._quality != 'VALID':
                        self._quality = 'ERROR'
                        self._error = stderr_text or 'PresentMon terminó la captura.'

    def _stop_capture(self):
        process = self._process
        self._process = None
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=1.0)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        self._cleanup_corepulse_session()

    def get_data(self):
        with self._lock:
            return {'fps': self._fps, 'frametime_ms': self._frametime_ms, 'fps_1pct_low': self._fps_1pct_low, 'process_id': self._target_pid, 'process_name': self._target_name, 'window_title': self._target_title, 'quality': self._quality, 'source': 'PresentMon ETW' if self._presentmon else None, 'presentmon_path': self.executable, 'session_name': COREPULSE_SESSION, 'sample_count': self._sample_count, 'error': self._error}

    def stop(self):
        self._running = False
        self._stop_capture()
