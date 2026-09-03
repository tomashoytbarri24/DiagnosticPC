"""Controla la duración adaptativa del diagnóstico según la evidencia real disponible."""
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
# Código refactorizado: nombres estables y documentación en español.
import time
from core.diagnostic_session import DiagnosticSession
POLICY = 'FAST_ADAPTIVE_EVIDENCE'
DEFAULT_MIN_SECONDS = 30
DEFAULT_MAX_SECONDS = 90
DEFAULT_MIN_SAMPLES = 25
DEFAULT_CONTEXT_STABILITY_SECONDS = 8
DEFAULT_ALERT_STABILITY_SECONDS = 12

def readiness_stage(info):
    """Gestiona la operación `readiness_stage` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    if not isinstance(info, dict):
        return 'Preparando evidencia'
    if info.get('ready'):
        return 'Evidencia suficiente'
    waiting = list(info.get('waiting_for') or [])
    if 'confirmando alertas' in waiting:
        return 'Confirmando condición'
    if 'observación de juego' in waiting or 'estabilizando contexto' in waiting:
        return 'Estabilizando contexto'
    if 'cobertura de sensores' in waiting:
        return 'Validando sensores'
    if 'muestras válidas' in waiting:
        return 'Recopilando muestras'
    return 'Analizando evidencia'

class AdaptiveDiagnosticSession(DiagnosticSession):
    """Clase responsable de `AdaptiveDiagnosticSession` dentro de CorePulse. Conserva los contratos de integridad del módulo."""

    def __init__(self, min_seconds=DEFAULT_MIN_SECONDS, max_seconds=DEFAULT_MAX_SECONDS, min_samples=DEFAULT_MIN_SAMPLES, context_stability_seconds=DEFAULT_CONTEXT_STABILITY_SECONDS, alert_stability_seconds=DEFAULT_ALERT_STABILITY_SECONDS):
        super().__init__(duration_seconds=max_seconds)
        self.min_seconds = max(30, int(min_seconds))
        self.max_seconds = max(self.min_seconds + 30, int(max_seconds))
        self.min_samples = max(DEFAULT_MIN_SAMPLES, int(min_samples))
        self.context_stability_seconds = max(5, int(context_stability_seconds))
        self.alert_stability_seconds = max(5, int(alert_stability_seconds))
        self._last_context = None
        self._context_since = None
        self._last_alert_signature = None
        self._alert_signature_since = None
        self._last_readiness = None

    def start(self):
        super().start()
        now = time.monotonic()
        self._last_context = None
        self._context_since = now
        self._last_alert_signature = None
        self._alert_signature_since = now
        self._last_readiness = None

    @staticmethod
    def _num(value):
        return isinstance(value, (int, float)) and (not isinstance(value, bool))

    def _samples_copy(self):
        with self._lock:
            return list(self._samples)

    def _coverage(self, samples):
        total = max(1, len(samples))
        cpu = sum((1 for sample in samples if self._num(sample.get('cpu_usage_percent')) or self._num(sample.get('cpu_package_temp_c')))) / total
        ram = sum((1 for sample in samples if self._num(sample.get('ram_usage_percent')))) / total
        return {'cpu': cpu, 'ram': ram}

    @staticmethod
    def _context(state):
        if not isinstance(state, dict):
            return 'UNKNOWN'
        return str(state.get('context') or state.get('mode') or 'UNKNOWN').upper()

    @staticmethod
    def _alert_signature(state):
        if not isinstance(state, dict):
            return ()
        alerts = state.get('alerts') or {}
        active = alerts.get('active') if isinstance(alerts, dict) else []
        output = []
        if isinstance(active, list):
            for item in active:
                if not isinstance(item, dict):
                    continue
                level = str(item.get('level') or '').upper()
                if level in {'WARNING', 'CRITICAL'}:
                    output.append((str(item.get('key') or item.get('title') or ''), level))
        return tuple(sorted(output))

    def _update_stability(self, state, now):
        context = self._context(state)
        if context != self._last_context:
            self._last_context = context
            self._context_since = now
        signature = self._alert_signature(state)
        if signature != self._last_alert_signature:
            self._last_alert_signature = signature
            self._alert_signature_since = now
        return (context, signature)

    def _target_seconds(self, context, alert_signature):
        target = self.min_seconds
        if context.startswith('GAME'):
            target = max(target, self.min_seconds + 15)
        if alert_signature:
            target = max(target, self.min_seconds + 30)
        return min(target, self.max_seconds)

    def readiness(self, state=None):
        now = time.monotonic()
        elapsed = float(self.elapsed_seconds())
        samples = self._samples_copy()
        coverage = self._coverage(samples)
        context, alert_signature = self._update_stability(state, now)
        context_stable = max(0.0, now - (self._context_since or now))
        alert_stable = max(0.0, now - (self._alert_signature_since or now))
        target = self._target_seconds(context, alert_signature)
        observation = (state or {}).get('observation') if isinstance(state, dict) else {}
        observation = observation if isinstance(observation, dict) else {}
        game_ok = True
        game_remaining = 0.0
        if context == 'GAME_OBSERVING':
            game_ok = False
            game_remaining = float(observation.get('remaining_seconds') or 0.0)
        elif context == 'GAME_ACTIVE' and observation:
            game_ok = bool(observation.get('complete', False))
            game_remaining = float(observation.get('remaining_seconds') or 0.0)
        context_ok = context in {'UNKNOWN', 'DESKTOP'} or context_stable >= self.context_stability_seconds
        if context == 'GAME_OBSERVING':
            context_ok = False
        alert_ok = not alert_signature or alert_stable >= self.alert_stability_seconds
        time_ok = elapsed >= target
        samples_ok = len(samples) >= self.min_samples
        cpu_ok = coverage['cpu'] >= 0.75
        ram_ok = coverage['ram'] >= 0.75
        ready = time_ok and samples_ok and cpu_ok and ram_ok and game_ok and context_ok and alert_ok
        max_reached = elapsed >= self.max_seconds
        p_time = min(1.0, elapsed / max(1, target))
        p_samples = min(1.0, len(samples) / max(1, self.min_samples))
        p_coverage = min(coverage['cpu'], coverage['ram'])
        p_context = 1.0 if game_ok and context_ok else 0.35
        p_alert = 1.0 if alert_ok else min(0.95, alert_stable / self.alert_stability_seconds)
        progress = 0.35 * p_time + 0.25 * p_samples + 0.2 * p_coverage + 0.1 * p_context + 0.1 * p_alert
        if ready:
            progress = 1.0
        elif max_reached:
            progress = max(progress, 0.99)
        remains = [max(0.0, target - elapsed), max(0.0, self.min_samples - len(samples)), max(0.0, self.context_stability_seconds - context_stable) if not context_ok else 0.0, max(0.0, self.alert_stability_seconds - alert_stable) if not alert_ok else 0.0, game_remaining]
        waiting = []
        if not time_ok:
            waiting.append('acumulando evidencia')
        if not samples_ok:
            waiting.append('muestras válidas')
        if not cpu_ok or not ram_ok:
            waiting.append('cobertura de sensores')
        if not game_ok:
            waiting.append('observación de juego')
        if not context_ok:
            waiting.append('estabilizando contexto')
        if not alert_ok:
            waiting.append('confirmando alertas')
        info = {'ready': ready, 'max_reached': max_reached, 'progress': round(max(0.0, min(1.0, progress)), 4), 'confidence_percent': round(max(0.0, min(100.0, progress * 100)), 1), 'eta_seconds': 0 if ready else int(round(max(remains))), 'elapsed_seconds': round(elapsed, 1), 'target_seconds': int(target), 'sample_count': len(samples), 'minimum_samples': int(self.min_samples), 'coverage': coverage, 'context': context, 'active_sustained_alerts': len(alert_signature), 'waiting_for': waiting, 'stage': readiness_stage({'ready': ready, 'waiting_for': waiting})}
        self._last_readiness = info
        return info

    def should_finish(self, state=None):
        if not self.active:
            return False
        info = self.readiness(state)
        return bool(info['ready'] or info['max_reached'])

    def remaining_seconds(self, state=None):
        return int(self.readiness(state)['eta_seconds'])

    def finish(self, state=None):
        info = self.readiness(state)
        actual = max(1, int(round(self.elapsed_seconds())))
        old_duration = self.duration_seconds
        self.duration_seconds = actual
        try:
            result = super().finish()
        finally:
            self.duration_seconds = old_duration
        if isinstance(result, dict):
            result['corepulse_version'] = VERSION
            result['session_valid'] = bool(info['ready'])
            result['completion_status'] = 'EVIDENCE_READY' if info['ready'] else 'SAFETY_CAP_PARTIAL'
            result['required_duration_seconds'] = None
            result['duration_policy'] = POLICY
            result['report_unlock_policy'] = 'EVIDENCE_READY_OR_SAFETY_CAP'
            result['adaptive_diagnostic'] = {**info, 'min_seconds': self.min_seconds, 'max_seconds': self.max_seconds, 'min_samples': self.min_samples, 'finish_reason': 'EVIDENCE_READY' if info['ready'] else 'MAX_TIME_REACHED'}
        return result
