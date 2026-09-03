"""Coordina la telemetría certificada y la publicación del overlay mediante RTSS."""
from __future__ import annotations
from core.version import VERSION_LABEL
# Código refactorizado: nombres estables y documentación en español.
import threading
import time
from collections import deque
from core.telemetry import get_system_telemetry
from core.rtss_osd import RTSSSharedMemory, start_rtss
from core.fps_certification import get_certified_fps
from core.overlay_theme import PANEL_BG, PANEL_FG, OSD_X, OSD_Y, OSD_PIXEL, build_original_overlay
from core.overlay_preferences import load_overlay_preferences
from core.hardware_policy import select_active_gpu

def _num(v):
    return isinstance(v, (int, float)) and (not isinstance(v, bool))

class RTSSOverlayService:

    def __init__(self):
        self.running = True
        self.rtss = RTSSSharedMemory()
        self._frametimes = deque(maxlen=1200)
        self._display_ft = deque(maxlen=5)
        self.last_error = None
        self.last_app = None
        self.last_text = None
        if not self.rtss.available:
            start_rtss()
            time.sleep(1.0)
        self.thread = threading.Thread(target=self._loop, daemon=True, name='CorePulse-RTSS')
        self.thread.start()

    def _one_percent_low(self):
        if len(self._frametimes) < 120:
            return None
        samples = list(self._frametimes)[-600:]
        count = max(1, int(len(samples) * 0.01))
        worst = sorted(samples, reverse=True)[:count]
        avg = sum(worst) / len(worst)
        return 1000.0 / avg if avg > 0 else None

    def _metrics(self, app):
        certified = get_certified_fps(rtss_app=app)
        ft = certified.get('frametime_ms')
        if _num(ft) and 0 < ft < 1000:
            self._frametimes.append(float(ft))
            self._display_ft.append(float(ft))
        smooth_ft = None
        if self._display_ft:
            smooth_ft = sum(self._display_ft) / len(self._display_ft)
        return {'fps': certified.get('fps'), 'frametime': smooth_ft, 'low_1': certified.get('fps_1pct_low') or self._one_percent_low(), 'fps_quality': certified.get('quality'), 'fps_source': certified.get('source'), 'fps_crosscheck': certified.get('crosscheck')}

    @staticmethod
    def _primary_gpu(gpus):
        return select_active_gpu(gpus)

    def _build_data(self, telemetry, app, game):
        cpu = telemetry.get('_cpu') or {}
        gpus = telemetry.get('_gpus') or []
        disks = telemetry.get('_storage_devices') or []
        gpu = self._primary_gpu(gpus)
        disk = disks[0] if disks else {}
        cpu_temp = cpu.get('package_temp_c')
        if not _num(cpu_temp):
            cpu_temp = telemetry.get('cpu_temp')
        cpu_ghz = cpu.get('clock_avg_ghz')
        if not _num(cpu_ghz):
            cpu_ghz = telemetry.get('cpu_ghz')
        gpu_usage = gpu.get('usage_percent')
        if not _num(gpu_usage):
            gpu_usage = telemetry.get('gpu_usage')
        gpu_temp = gpu.get('temperature_c')
        if not _num(gpu_temp):
            gpu_temp = telemetry.get('gpu_temp')
        return {'exe': str(app.get('name') or '').replace('\\', '/').split('/')[-1], 'fps': game['fps'], 'frametime': game['frametime'], 'low_1': game['low_1'], 'cpu_usage': telemetry.get('cpu_usage'), 'cpu_temp': cpu_temp, 'cpu_ghz': cpu_ghz, 'ram_usage': telemetry.get('ram_usage'), 'gpu_usage': gpu_usage, 'gpu_temp': gpu_temp, 'gpu_hotspot': gpu.get('hotspot_c'), 'ssd_temp': disk.get('temperature_c'), 'ssd_life': disk.get('life_percent')}

    def _loop(self):
        while self.running:
            try:
                if not self.rtss.available:
                    self.last_error = 'RTSS Shared Memory no disponible'
                    time.sleep(1.0)
                    continue
                app = self.rtss.active_app(freshness_ms=2500)
                self.last_app = app
                if app.get('quality') != 'VALID':
                    self.rtss.update_osd('<C0=00E5FF><C4=8EA0B8>\r<C0>COREPULSE<C>\n<C4>Esperando aplicacion 3D activa...<C>')
                    self.last_error = 'Esperando aplicación 3D activa'
                    time.sleep(0.5)
                    continue
                prefs = load_overlay_preferences()
                if hasattr(self.rtss, 'set_app_osd_style'):
                    self.rtss.set_app_osd_style(app_index=app.get('index'), x=prefs.get('x', OSD_X), y=prefs.get('y', OSD_Y), pixel=prefs.get('pixel', OSD_PIXEL), color=PANEL_FG, background=PANEL_BG)
                game = self._metrics(app)
                telemetry = get_system_telemetry()
                payload = self._build_data(telemetry, app, game)
                text = build_original_overlay(payload, prefs)
                self.last_text = text
                if self.rtss.update_osd(text):
                    self.last_error = None
                else:
                    self.last_error = self.rtss.last_error or 'Error escribiendo OSD'
            except Exception as exc:
                self.last_error = f'{type(exc).__name__}: {exc}'
            time.sleep(0.5)

    def status(self):
        return {'running': self.running, 'rtss_available': self.rtss.available, 'rtss_version': self.rtss.version, 'active_app': self.last_app, 'last_error': self.last_error, 'last_text': self.last_text, 'theme': f'CorePulse Configurable Dark Blue {VERSION_LABEL}', 'preferences': load_overlay_preferences(), 'one_percent_low_ready': len(self._frametimes) >= 120, 'fps_policy': 'REAL_FPS_OR_NA_ONLY'}

    def stop(self):
        self.running = False
        try:
            self.thread.join(timeout=1.5)
        except Exception:
            pass
        try:
            self.rtss.close()
        except Exception:
            pass
