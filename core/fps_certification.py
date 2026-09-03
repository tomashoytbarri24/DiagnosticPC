"""Certifica FPS y frametime reales usando RTSS y PresentMon bajo la política REAL_FPS_OR_NA_ONLY."""
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
# Código refactorizado: nombres estables y documentación en español.
import math
import threading
import time
from pathlib import Path
from core.rtss_osd import RTSSSharedMemory, start_rtss
from core.presentmon_fps import PresentMonFPS
from core.presentmon_same_pid import PresentMonSamePIDCapture
POLICY = 'REAL_FPS_OR_NA_ONLY'
RTSS_FRESHNESS_MS = 2500
PRESENTMON_MIN_SAMPLES_FOR_CROSSCHECK = 15

def _finite(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        v = float(value)
    except Exception:
        return None
    return v if math.isfinite(v) else None

def _fps_plausible(value):
    v = _finite(value)
    return v is not None and 0.0 < v <= 2000.0

def _frametime_plausible(value):
    v = _finite(value)
    return v is not None and 0.0 < v < 1000.0

class CertifiedFPSProvider:

    def __init__(self, project_root=None):
        self.project_root = Path(project_root or Path(__file__).resolve().parents[1])
        self._lock = threading.RLock()
        self.rtss = RTSSSharedMemory()
        if not self.rtss.available:
            start_rtss()
            time.sleep(0.8)
        self.presentmon = PresentMonFPS(project_root=self.project_root)
        self.presentmon_samepid = PresentMonSamePIDCapture(project_root=self.project_root)
        self.last = self._empty('UNAVAILABLE', 'NO_CAPTURE_YET')

    @staticmethod
    def _empty(quality, reason):
        return {'version': VERSION, 'policy': POLICY, 'fps': None, 'fps_instant': None, 'frametime_ms': None, 'fps_1pct_low': None, 'pid': None, 'process_name': None, 'quality': quality, 'reason': reason, 'source': None, 'source_primary': 'RTSS Shared Memory', 'source_crosscheck': 'PresentMon ETW', 'rtss_age_ms': None, 'sensor_timestamp': None, 'snapshot_timestamp': time.time(), 'presentmon': None, 'crosscheck': None, 'synthetic': False, 'estimated': False, 'interpolated': False}

    def _rtss_app(self):
        if not self.rtss.available:
            return None
        app = self.rtss.active_app(freshness_ms=RTSS_FRESHNESS_MS)
        return app if isinstance(app, dict) else None

    @staticmethod
    def _compare(rtss_fps, pm_fps):
        r = _finite(rtss_fps)
        p = _finite(pm_fps)
        if not _fps_plausible(r) or not _fps_plausible(p):
            return {'available': False, 'agreement': None, 'delta_fps': None, 'delta_percent': None, 'reason': 'INSUFFICIENT_VALID_DATA'}
        delta = abs(r - p)
        baseline = max(abs(r), abs(p), 1.0)
        pct = 100.0 * delta / baseline
        agreement = delta <= 10.0 or pct <= 15.0
        return {'available': True, 'agreement': agreement, 'delta_fps': round(delta, 3), 'delta_percent': round(pct, 3), 'reason': None if agreement else 'RTSS_PRESENTMON_WINDOW_MISMATCH'}

    def get_snapshot(self, rtss_app=None):
        with self._lock:
            now = time.time()
            app = rtss_app if isinstance(rtss_app, dict) else self._rtss_app()
            if not app or app.get('quality') != 'VALID':
                self.last = self._empty('UNAVAILABLE', 'NO_FRESH_3D_APP_IN_RTSS')
                return dict(self.last)
            fps_1s = _finite(app.get('fps_1s'))
            fps_inst = _finite(app.get('fps'))
            frametime = _finite(app.get('frametime_ms'))
            low_1 = _finite(app.get('fps_1pct_low'))
            age_ms = _finite(app.get('age_ms'))
            fps = fps_1s if _fps_plausible(fps_1s) else fps_inst
            if not _fps_plausible(fps):
                self.last = self._empty('UNAVAILABLE', 'RTSS_FPS_NOT_VALID')
                return dict(self.last)
            if not _frametime_plausible(frametime):
                frametime = None
            pid = app.get('pid')
            name = app.get('name')
            sensor_ts = now - age_ms / 1000.0 if age_ms is not None and age_ms >= 0 else None
            pm = self.presentmon_samepid.read(pid)
            pm_pid = pm.get('pid')
            pm_samples = int(pm.get('sample_count') or 0)
            same_pid = bool(pid and pm_pid and (int(pid) == int(pm_pid)))
            pm_valid = same_pid and pm.get('quality') == 'VALID' and (pm_samples >= PRESENTMON_MIN_SAMPLES_FOR_CROSSCHECK) and _fps_plausible(pm.get('fps'))
            cross = self._compare(fps, pm.get('fps')) if pm_valid else {'available': False, 'agreement': None, 'delta_fps': None, 'delta_percent': None, 'reason': 'PRESENTMON_DIFFERENT_PID' if pm_pid and (not same_pid) else 'PRESENTMON_NOT_READY'}
            quality = 'VALID_CROSSCHECKED' if cross.get('agreement') is True else 'VALID_RTSS'
            reason = None
            if cross.get('available') and cross.get('agreement') is False:
                quality = 'VALID_RTSS_CROSSCHECK_WARNING'
                reason = cross.get('reason')
            result = {'version': VERSION, 'policy': POLICY, 'fps': round(float(fps), 3), 'fps_instant': round(float(fps_inst), 3) if _fps_plausible(fps_inst) else None, 'frametime_ms': round(float(frametime), 3) if frametime is not None else None, 'fps_1pct_low': round(float(low_1), 3) if _fps_plausible(low_1) else None, 'pid': int(pid) if pid else None, 'process_name': name, 'quality': quality, 'reason': reason, 'source': 'RTSS Shared Memory', 'source_primary': 'RTSS Shared Memory', 'source_crosscheck': 'PresentMon ETW', 'rtss_age_ms': age_ms, 'sensor_timestamp': sensor_ts, 'snapshot_timestamp': now, 'presentmon': {'quality': pm.get('quality'), 'pid': pm_pid, 'process_name': name if same_pid else None, 'fps': pm.get('fps'), 'frametime_ms': pm.get('frametime_ms'), 'fps_1pct_low': pm.get('fps_1pct_low'), 'sample_count': pm_samples, 'path': str(self.project_root / 'tools' / 'presentmon' / 'PresentMon.exe'), 'same_pid': same_pid, 'error': pm.get('error')}, 'crosscheck': cross, 'synthetic': False, 'estimated': False, 'interpolated': False}
            self.last = result
            return dict(result)

    def runtime_capability(self):
        pm = self.presentmon.get_data()
        rtss_diag = self.rtss.raw_diagnostic()
        return {'version': VERSION, 'policy': POLICY, 'rtss': {'available': bool(rtss_diag.get('ok')), 'version': self.rtss.version if rtss_diag.get('ok') else None, 'diagnostic': rtss_diag}, 'presentmon': {'available': bool(pm.get('presentmon_path')), 'path': str(self.project_root / 'tools' / 'presentmon' / 'PresentMon.exe'), 'quality': pm.get('quality'), 'error': pm.get('error')}, 'rules': {'primary_source': 'RTSS Shared Memory', 'presentmon_is_crosscheck_only': True, 'no_refresh_rate_fallback': True, 'no_estimated_fps': True, 'no_interpolation': True, 'missing_real_fps_means_na': True}}

    def stop(self):
        try:
            self.presentmon.stop()
        except Exception:
            pass
        try:
            self.presentmon_samepid.stop()
        except Exception:
            pass
        try:
            self.rtss.close()
        except Exception:
            pass
_SINGLETON = None
_SINGLETON_LOCK = threading.Lock()

def get_fps_provider():
    global _SINGLETON
    with _SINGLETON_LOCK:
        if _SINGLETON is None:
            _SINGLETON = CertifiedFPSProvider()
        return _SINGLETON

def get_certified_fps(rtss_app=None):
    return get_fps_provider().get_snapshot(rtss_app=rtss_app)

def get_fps_runtime_capability():
    return get_fps_provider().runtime_capability()

def stop_fps_provider():
    global _SINGLETON
    with _SINGLETON_LOCK:
        provider = _SINGLETON
        _SINGLETON = None
    if provider is not None:
        provider.stop()
