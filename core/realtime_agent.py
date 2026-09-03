"""Ejecuta el agente de monitoreo continuo y combina telemetría, contexto y alertas."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import copy
import ctypes
import os
import threading
import time
from collections import deque
from core.telemetry import get_system_telemetry
from core.hardware_policy import select_active_gpu
from core.rtss_osd import RTSSSharedMemory
from core.fps_certification import get_certified_fps
from core.alert_engine import IntelligentAlertEngine
from core.agent_reaction import instant_health_from_sample
IS_WINDOWS = os.name == 'nt'
SAMPLE_INTERVAL = 1.0
OBSERVATION_SECONDS = 30
BACKGROUND_GRACE_SECONDS = 2

def _num(value):
    return isinstance(value, (int, float)) and (not isinstance(value, bool))

def _foreground_pid():
    if not IS_WINDOWS:
        return None
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)
    except Exception:
        return None

class RealTimeAgent:

    def __init__(self):
        self.running = True
        self.rtss = RTSSSharedMemory()
        self.alert_engine = IntelligentAlertEngine()
        self.lock = threading.RLock()
        self.samples = deque(maxlen=300)
        self.session_pid = None
        self.session_started_at = None
        self.foreground_started_at = None
        self.background_started_at = None
        self.latest_state = {'mode': 'DESKTOP', 'context': 'DESKTOP', 'game_detected': False, 'game_foreground': False, 'game': None, 'overall': 'UNKNOWN', 'instant': {'severity': 'UNKNOWN', 'status': 'NO EVALUABLE', 'reasons': [], 'source': 'REALTIME_AGENT_CURRENT_SAMPLE', 'synthetic': False, 'estimated': False}, 'observation': None, 'alerts': {'active': [], 'history': [], 'active_count': 0, 'history_count': 0}, 'findings': [], 'timestamp': time.time()}
        self.thread = threading.Thread(target=self._loop, daemon=True, name='CorePulse-RealtimeAgent')
        self.thread.start()

    def _rtss_game(self):
        try:
            app = self.rtss.active_app(freshness_ms=2500)
            if app.get('quality') == 'VALID':
                certified = get_certified_fps(rtss_app=app)
                if certified.get('quality') in {'VALID_RTSS', 'VALID_CROSSCHECKED', 'VALID_RTSS_CROSSCHECK_WARNING'}:
                    merged = dict(app)
                    merged['fps_1s'] = certified.get('fps')
                    merged['fps'] = certified.get('fps_instant')
                    merged['frametime_ms'] = certified.get('frametime_ms')
                    merged['fps_1pct_low'] = certified.get('fps_1pct_low')
                    merged['fps_quality'] = certified.get('quality')
                    merged['fps_source'] = certified.get('source')
                    merged['fps_crosscheck'] = certified.get('crosscheck')
                    return merged
        except Exception:
            pass
        return None

    def _reset_session(self):
        self.session_pid = None
        self.session_started_at = None
        self.foreground_started_at = None
        self.background_started_at = None

    def _context(self, game):
        now = time.time()
        if not game:
            self._reset_session()
            return {'context': 'DESKTOP', 'foreground': False, 'foreground_pid': _foreground_pid(), 'session_seconds': 0.0, 'foreground_seconds': 0.0, 'background_seconds': 0.0, 'observation_remaining': 0.0}
        pid = int(game.get('pid') or 0)
        foreground_pid = _foreground_pid()
        foreground = bool(pid and foreground_pid and (pid == foreground_pid))
        if pid != self.session_pid:
            self.session_pid = pid
            self.session_started_at = now
            self.foreground_started_at = now if foreground else None
            self.background_started_at = None if foreground else now
        if foreground:
            if self.foreground_started_at is None:
                self.foreground_started_at = now
            self.background_started_at = None
        else:
            if self.background_started_at is None:
                self.background_started_at = now
            self.foreground_started_at = None
        session_seconds = max(0.0, now - (self.session_started_at or now))
        foreground_seconds = max(0.0, now - self.foreground_started_at) if self.foreground_started_at is not None else 0.0
        background_seconds = max(0.0, now - self.background_started_at) if self.background_started_at is not None else 0.0
        if not foreground and background_seconds >= BACKGROUND_GRACE_SECONDS:
            context = 'GAME_BACKGROUND'
        elif foreground and foreground_seconds >= OBSERVATION_SECONDS:
            context = 'GAME_ACTIVE'
        else:
            context = 'GAME_OBSERVING'
        return {'context': context, 'foreground': foreground, 'foreground_pid': foreground_pid, 'session_seconds': round(session_seconds, 1), 'foreground_seconds': round(foreground_seconds, 1), 'background_seconds': round(background_seconds, 1), 'observation_remaining': round(max(0.0, OBSERVATION_SECONDS - foreground_seconds), 1)}

    @staticmethod
    def _primary_gpu(gpus):
        return select_active_gpu(gpus)

    def _sample(self):
        telemetry = get_system_telemetry()
        game = self._rtss_game()
        context = self._context(game)
        cpu = telemetry.get('_cpu') or {}
        gpus = telemetry.get('_gpus') or []
        disks = telemetry.get('_storage_devices') or []
        gpu = self._primary_gpu(gpus)
        disk = disks[0] if disks else {}
        return {'timestamp': time.time(), 'mode': 'GAME' if game else 'DESKTOP', 'context': context['context'], 'game_foreground': context['foreground'], 'foreground_pid': context['foreground_pid'], 'session_seconds': context['session_seconds'], 'foreground_seconds': context['foreground_seconds'], 'background_seconds': context['background_seconds'], 'observation_remaining': context['observation_remaining'], 'game': copy.deepcopy(game), 'cpu_usage': telemetry.get('cpu_usage'), 'cpu_temp': cpu.get('package_temp_c', telemetry.get('cpu_temp')), 'cpu_tjmax_distance': cpu.get('distance_to_tjmax_min_c'), 'ram_usage': telemetry.get('ram_usage'), 'gpu_usage': gpu.get('usage_percent', telemetry.get('gpu_usage')), 'gpu_temp': gpu.get('temperature_c', telemetry.get('gpu_temp')), 'gpu_hotspot': gpu.get('hotspot_c'), 'ssd_temp': disk.get('temperature_c'), 'ssd_warning': disk.get('warning_temperature_c'), 'ssd_critical': disk.get('critical_temperature_c'), 'fps': game.get('fps_1s') if game else None, 'fps_instant': game.get('fps') if game else None, 'frametime_ms': game.get('frametime_ms') if game else None}

    def _base_findings(self, sample, alerts, instant=None):
        findings = []
        context = sample['context']
        for alert in alerts['active']:
            findings.append({'component': alert['component'], 'level': alert['level'], 'title': alert['title'], 'detail': alert['detail'], 'evidence': alert['evidence'], 'context': context, 'alert_key': alert['key'], 'active': True})
        instant = instant if isinstance(instant, dict) else {}
        instant_level = str(instant.get('severity') or 'UNKNOWN').upper()
        instant_reasons = [str(x) for x in (instant.get('reasons') or []) if x]
        instant_attention = instant_level in {'ELEVATED', 'WARNING', 'CRITICAL', 'ERROR'}
        if instant_attention and not alerts.get('active'):
            reason = instant_reasons[0] if instant_reasons else str(instant.get('status') or 'Condición instantánea')
            component = 'CPU' if 'CPU' in reason.upper() else 'GPU' if 'GPU' in reason.upper() else 'SYSTEM'
            findings.append({'component': component, 'level': 'OBSERVING', 'title': 'Condición instantánea en observación', 'detail': f'{reason}. El agente está confirmando si la condición persiste antes de crear una alerta sostenida.', 'evidence': instant_reasons, 'context': context, 'active': True, 'provisional': True})
        if context == 'GAME_BACKGROUND':
            findings.append({'component': 'GAME', 'level': 'INFO', 'title': 'Juego en segundo plano', 'detail': 'FPS y frametime no son evaluables mientras el juego no está en foreground.', 'evidence': ['FPS: NO EVALUABLE', 'Frametime: NO EVALUABLE'], 'context': context, 'active': True})
        elif context == 'GAME_OBSERVING':
            findings.append({'component': 'SYSTEM', 'level': 'OBSERVING', 'title': 'Analizando sesión de juego', 'detail': 'CorePulse está acumulando 30 segundos de evidencia foreground.', 'evidence': [f"Foreground: {sample['foreground_seconds']:.0f}/{OBSERVATION_SECONDS} s", f"Restante: {sample['observation_remaining']:.0f} s"], 'context': context, 'active': True})
        elif context == 'GAME_ACTIVE':
            if not any((finding['level'] in {'WARNING', 'CRITICAL'} for finding in findings)):
                findings.append({'component': 'SYSTEM', 'level': 'NORMAL', 'title': 'Sesión de juego sin alertas críticas activas', 'detail': 'El motor no mantiene warnings o criticals activos en este instante.', 'evidence': [f"FPS RTSS: {sample['fps']:.1f}" if _num(sample.get('fps')) else 'FPS RTSS: N/A', f"CPU: {sample['cpu_temp']} °C" if _num(sample.get('cpu_temp')) else 'CPU: N/A', f"GPU: {sample['gpu_temp']} °C" if _num(sample.get('gpu_temp')) else 'GPU: N/A'], 'context': context, 'active': True})
        elif context == 'DESKTOP':
            if not instant_attention and not any((finding['level'] in {'WARNING', 'CRITICAL'} for finding in findings)):
                findings.append({'component': 'SYSTEM', 'level': 'NORMAL', 'title': 'Sistema estable en segundo plano', 'detail': 'No hay warnings o criticals persistentes activos.', 'evidence': [], 'context': context, 'active': True})
        return findings

    def _overall(self, context, alerts):
        alert_overall = self.alert_engine.overall()
        if alert_overall in {'CRITICAL', 'WARNING'}:
            return alert_overall
        if context == 'GAME_OBSERVING':
            return 'OBSERVING'
        if context == 'GAME_BACKGROUND':
            return 'INFO'
        if alert_overall == 'INFO':
            return 'INFO'
        return 'NORMAL'

    def _loop(self):
        while self.running:
            try:
                sample = self._sample()
                with self.lock:
                    self.samples.append(sample)
                alerts = self.alert_engine.evaluate(sample)
                instant = instant_health_from_sample(sample)
                observation = None
                if sample['mode'] == 'GAME':
                    observation = {'required_seconds': OBSERVATION_SECONDS, 'foreground_seconds': sample['foreground_seconds'], 'remaining_seconds': sample['observation_remaining'], 'complete': sample['context'] == 'GAME_ACTIVE'}
                state = {'mode': sample['mode'], 'context': sample['context'], 'game_detected': sample['mode'] == 'GAME', 'game_foreground': sample['game_foreground'], 'game': copy.deepcopy(sample['game']), 'overall': self._overall(sample['context'], alerts), 'instant': instant, 'observation': observation, 'alerts': alerts, 'findings': self._base_findings(sample, alerts, instant), 'sample': copy.deepcopy(sample), 'timestamp': time.time()}
                with self.lock:
                    self.latest_state = state
            except Exception as exc:
                with self.lock:
                    self.latest_state = {'mode': 'UNKNOWN', 'context': 'UNKNOWN', 'game_detected': False, 'game_foreground': False, 'game': None, 'overall': 'ERROR', 'instant': {'severity': 'UNKNOWN', 'status': 'NO EVALUABLE', 'reasons': [], 'source': 'REALTIME_AGENT_CURRENT_SAMPLE', 'synthetic': False, 'estimated': False}, 'observation': None, 'alerts': {'active': [], 'history': [], 'active_count': 0, 'history_count': 0}, 'findings': [{'component': 'AGENT', 'level': 'ERROR', 'title': 'Error del Intelligent Alert Engine', 'detail': f'{type(exc).__name__}: {exc}', 'evidence': [], 'context': 'UNKNOWN', 'active': True}], 'timestamp': time.time()}
            time.sleep(SAMPLE_INTERVAL)

    def get_state(self):
        with self.lock:
            return copy.deepcopy(self.latest_state)

    def get_alert_history(self):
        return copy.deepcopy(self.alert_engine.snapshot()['history'])

    def stop(self):
        self.running = False
        try:
            self.thread.join(timeout=2.0)
        except Exception:
            pass
        try:
            self.rtss.close()
        except Exception:
            pass
