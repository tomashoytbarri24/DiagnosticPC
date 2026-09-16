"""Evalúa ventanas de evidencia y genera alertas técnicas basadas en telemetría real."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import copy
import time
from collections import deque
from dataclasses import dataclass, asdict

def _num(v):
    return isinstance(v, (int, float)) and (not isinstance(v, bool))

@dataclass
class AlertEvent:
    key: str
    component: str
    level: str
    title: str
    detail: str
    evidence: list[str]
    context: str
    first_seen: float
    last_seen: float
    active: bool
    occurrences: int
    resolved_at: float | None = None

class IntelligentAlertEngine:

    def __init__(self):
        self._active = {}
        self._history = deque(maxlen=250)
        self._samples = deque(maxlen=180)

    def _recent(self, count, contexts=None):
        values = list(self._samples)[-count:]
        if contexts:
            contexts = set(contexts)
            values = [s for s in values if s.get('context') in contexts]
        return values

    @staticmethod
    def _ratio(samples, predicate):
        valid = []
        matched = 0
        for s in samples:
            result = predicate(s)
            if result is None:
                continue
            valid.append(result)
            if result:
                matched += 1
        return (matched, len(valid))

    def _activate(self, key, component, level, title, detail, evidence, context, now):
        event = self._active.get(key)
        if event:
            event.level = level
            event.title = title
            event.detail = detail
            event.evidence = list(evidence)
            event.context = context
            event.last_seen = now
            event.occurrences += 1
            return
        self._active[key] = AlertEvent(key=key, component=component, level=level, title=title, detail=detail, evidence=list(evidence), context=context, first_seen=now, last_seen=now, active=True, occurrences=1)

    def _resolve(self, key, now):
        event = self._active.pop(key, None)
        if event is None:
            return
        event.active = False
        event.resolved_at = now
        event.last_seen = now
        self._history.appendleft(copy.deepcopy(event))

    def _sync_rule(self, *, key, active_condition, clear_condition, component, level, title, detail, evidence, context, now):
        if active_condition:
            self._activate(key, component, level, title, detail, evidence, context, now)
            return
        if key in self._active and clear_condition:
            self._resolve(key, now)

    def evaluate(self, sample):
        now = time.time()
        context = sample.get('context', 'UNKNOWN')
        self._samples.append(copy.deepcopy(sample))
        from statistics import median
        cpu30 = self._recent(30)
        cpu12 = self._recent(12)

        def _tj_distance(sample):
            value = sample.get('cpu_tjmax_distance')
            return float(value) if _num(value) else None

        def _inferred_tjmax(sample):
            temp = sample.get('cpu_temp')
            distance = sample.get('cpu_tjmax_distance')
            if not (_num(temp) and _num(distance)):
                return None
            return float(temp) + float(distance)
        inferred_values = [value for value in (_inferred_tjmax(sample) for sample in cpu30) if value is not None]
        tjmax_reference = median(inferred_values) if inferred_values else None
        consistent_tjmax = []
        if tjmax_reference is not None:
            consistent_tjmax = [value for value in inferred_values if abs(value - tjmax_reference) <= 2.0]
        sensor_consistency = len(consistent_tjmax) / len(inferred_values) if inferred_values else 0.0
        sensor_valid = len(inferred_values) >= 20 and sensor_consistency >= 0.8 and (80.0 <= tjmax_reference <= 115.0) if tjmax_reference is not None else False
        near2, valid12 = self._ratio(cpu12, lambda s: _tj_distance(s) <= 2 if _tj_distance(s) is not None else None)
        safe5_12, safe5_valid12 = self._ratio(cpu12, lambda s: _tj_distance(s) > 5 if _tj_distance(s) is not None else None)
        near5, valid30 = self._ratio(cpu30, lambda s: _tj_distance(s) <= 5 if _tj_distance(s) is not None else None)
        near10, valid10 = self._ratio(cpu30, lambda s: 5 < _tj_distance(s) <= 10 if _tj_distance(s) is not None else None)
        safe10, safe10_valid = self._ratio(cpu30, lambda s: _tj_distance(s) > 10 if _tj_distance(s) is not None else None)
        cpu_temp = sample.get('cpu_temp')
        tj = sample.get('cpu_tjmax_distance')
        cpu_critical = sensor_valid and valid12 >= 10 and (near2 >= 8)
        cpu_critical_clear = safe5_valid12 >= 8 and safe5_12 >= 8
        self._sync_rule(key='cpu_tjmax_critical', active_condition=cpu_critical, clear_condition=cpu_critical_clear, component='CPU', level='CRITICAL', title='CPU extremadamente cerca de TjMax', detail='La CPU estuvo a 2 °C o menos de TjMax en una proporción alta de las últimas 12 muestras y la referencia térmica inferida fue consistente.', evidence=[f'CPU actual: {cpu_temp} °C' if _num(cpu_temp) else 'CPU actual: N/A', f'Distancia actual: {tj} °C' if _num(tj) else 'Distancia actual: N/A', f'Evidencia extrema: {near2}/{valid12} muestras', f'TjMax inferido: {tjmax_reference:.1f} °C' if tjmax_reference is not None else 'TjMax inferido: N/A', f'Consistencia sensor: {sensor_consistency * 100:.1f}%', 'Regla CRITICAL: <=2 °C de TjMax en >=8/12 muestras válidas.'], context=context, now=now)
        cpu_warning = not cpu_critical and sensor_valid and (valid30 >= 24) and (near5 >= 20 or near10 >= 20)
        cpu_warning_clear = safe10_valid >= 20 and safe10 >= 18
        warning_band = '<=5 °C' if near5 >= 20 else '5-10 °C'
        warning_hits = near5 if near5 >= 20 else near10
        self._sync_rule(key='cpu_tjmax_warning', active_condition=cpu_warning, clear_condition=cpu_warning_clear or cpu_critical, component='CPU', level='WARNING', title='CPU muy cerca de TjMax de forma sostenida', detail='La CPU se mantuvo cerca de TjMax durante una proporción alta de la ventana de observación.', evidence=[f'CPU actual: {cpu_temp} °C' if _num(cpu_temp) else 'CPU actual: N/A', f'Distancia actual: {tj} °C' if _num(tj) else 'Distancia actual: N/A', f'Rango observado: {warning_band}', f'Evidencia térmica: {warning_hits}/{valid30} muestras', f'TjMax inferido: {tjmax_reference:.1f} °C' if tjmax_reference is not None else 'TjMax inferido: N/A', f'Consistencia sensor: {sensor_consistency * 100:.1f}%'], context=context, now=now)
        sensor_uncertain = len(inferred_values) >= 20 and (not sensor_valid) and (near5 >= 15 or near2 >= 6)
        self._sync_rule(key='cpu_tjmax_sensor_uncertain', active_condition=sensor_uncertain, clear_condition=sensor_valid, component='CPU', level='INFO', title='Referencia térmica de CPU inconsistente', detail='CorePulse detectó lecturas térmicas cercanas al límite, pero la referencia TjMax inferida no fue suficientemente consistente para elevar una alerta crítica.', evidence=[f'TjMax inferido mediano: {tjmax_reference:.1f} °C' if tjmax_reference is not None else 'TjMax inferido: N/A', f'Consistencia: {sensor_consistency * 100:.1f}%', f'Muestras de referencia: {len(inferred_values)}'], context=context, now=now)
        ram15 = self._recent(15)
        high_ram, valid_ram = self._ratio(ram15, lambda s: s['ram_usage'] >= 95 if _num(s.get('ram_usage')) else None)
        ram_normal, valid_ram_normal = self._ratio(ram15, lambda s: s['ram_usage'] < 90 if _num(s.get('ram_usage')) else None)
        ram = sample.get('ram_usage')
        self._sync_rule(key='ram_pressure', active_condition=valid_ram >= 12 and high_ram >= 12, clear_condition=valid_ram_normal >= 10 and ram_normal >= 10, component='RAM', level='WARNING', title='Presión de RAM sostenida', detail='La RAM estuvo en 95% o más en la gran mayoría de las últimas 15 muestras.', evidence=[f'RAM actual: {ram}%' if _num(ram) else 'RAM actual: N/A', f'Evidencia: {high_ram}/{valid_ram} muestras'], context=context, now=now)
        st = sample.get('ssd_temp')
        sw = sample.get('ssd_warning')
        sc = sample.get('ssd_critical')
        ssd15 = self._recent(15)
        if _num(sc):
            crit_count, crit_valid = self._ratio(ssd15, lambda s: s['ssd_temp'] >= sc if _num(s.get('ssd_temp')) else None)
            safe_count, safe_valid = self._ratio(ssd15, lambda s: s['ssd_temp'] < sc - 3 if _num(s.get('ssd_temp')) else None)
            self._sync_rule(key='ssd_critical', active_condition=crit_valid >= 5 and crit_count >= 3, clear_condition=safe_valid >= 8 and safe_count >= 8, component='SSD', level='CRITICAL', title='SSD sobre umbral crítico', detail='La unidad alcanzó repetidamente el umbral crítico reportado por el propio dispositivo.', evidence=[f'SSD actual: {st} °C' if _num(st) else 'SSD actual: N/A', f'Crítico reportado: {sc} °C', f'Evidencia: {crit_count}/{crit_valid} muestras'], context=context, now=now)
        if _num(sw):
            warn_count, warn_valid = self._ratio(ssd15, lambda s: s['ssd_temp'] >= sw if _num(s.get('ssd_temp')) else None)
            safe_warn_count, safe_warn_valid = self._ratio(ssd15, lambda s: s['ssd_temp'] < sw - 3 if _num(s.get('ssd_temp')) else None)
            self._sync_rule(key='ssd_warning', active_condition=warn_valid >= 8 and warn_count >= 6 and (not (_num(sc) and _num(st) and (st >= sc))), clear_condition=safe_warn_valid >= 8 and safe_warn_count >= 8, component='SSD', level='WARNING', title='SSD sobre umbral de advertencia', detail='La temperatura superó repetidamente el warning reportado por la propia unidad.', evidence=[f'SSD actual: {st} °C' if _num(st) else 'SSD actual: N/A', f'Warning reportado: {sw} °C', f'Evidencia: {warn_count}/{warn_valid} muestras'], context=context, now=now)
        gpu_usage = sample.get('gpu_usage')
        gpu_temp = sample.get('gpu_temp')
        gpu_hotspot = sample.get('gpu_hotspot')
        game_context = context in {'GAME_OBSERVING', 'GAME_ACTIVE'}
        gpu10 = self._recent(10, contexts={'GAME_OBSERVING', 'GAME_ACTIVE'})
        high_gpu, valid_gpu = self._ratio(gpu10, lambda s: s['gpu_usage'] >= 90 if _num(s.get('gpu_usage')) else None)
        self._sync_rule(key='gpu_high_load_info', active_condition=game_context and valid_gpu >= 6 and (high_gpu >= 5), clear_condition=not game_context or (valid_gpu >= 6 and high_gpu <= 2), component='GPU', level='INFO', title='GPU trabajando a alta carga', detail='Una GPU al 90–100% durante un juego puede ser normal si temperaturas y estabilidad son adecuadas.', evidence=[f'Uso GPU actual: {gpu_usage}%' if _num(gpu_usage) else 'Uso GPU: N/A', f'Core: {gpu_temp} °C' if _num(gpu_temp) else 'Core: N/A', f'Hotspot: {gpu_hotspot} °C' if _num(gpu_hotspot) else 'Hotspot: N/A', f'Evidencia carga alta: {high_gpu}/{valid_gpu}'], context=context, now=now)
        hotspot15 = self._recent(15, contexts={'GAME_OBSERVING', 'GAME_ACTIVE'})
        hotspot_high, hotspot_valid = self._ratio(hotspot15, lambda s: s['gpu_hotspot'] >= 100 if _num(s.get('gpu_hotspot')) else None)
        hotspot_safe, hotspot_safe_valid = self._ratio(hotspot15, lambda s: s['gpu_hotspot'] < 95 if _num(s.get('gpu_hotspot')) else None)
        delta = None
        if _num(gpu_hotspot) and _num(gpu_temp):
            delta = gpu_hotspot - gpu_temp
        self._sync_rule(key='gpu_hotspot_attention', active_condition=game_context and hotspot_valid >= 12 and (hotspot_high >= 12), clear_condition=not game_context or (hotspot_safe_valid >= 10 and hotspot_safe >= 10), component='GPU', level='WARNING', title='GPU Hotspot alto de forma sostenida', detail='El hotspot estuvo en 100 °C o más en la mayoría de las últimas 15 muestras. Es una heurística conservadora de CorePulse, no un límite oficial.', evidence=[f'Hotspot actual: {gpu_hotspot} °C' if _num(gpu_hotspot) else 'Hotspot: N/A', f'Core actual: {gpu_temp} °C' if _num(gpu_temp) else 'Core: N/A', f'Delta actual: {delta:.1f} °C' if _num(delta) else 'Delta: N/A', f'Evidencia: {hotspot_high}/{hotspot_valid} muestras'], context=context, now=now)
        delta20 = self._recent(20, contexts={'GAME_OBSERVING', 'GAME_ACTIVE'})
        delta_high, delta_valid = self._ratio(delta20, lambda s: s['gpu_hotspot'] - s['gpu_temp'] >= 25 if _num(s.get('gpu_hotspot')) and _num(s.get('gpu_temp')) else None)
        delta_safe, delta_safe_valid = self._ratio(delta20, lambda s: s['gpu_hotspot'] - s['gpu_temp'] < 20 if _num(s.get('gpu_hotspot')) and _num(s.get('gpu_temp')) else None)
        self._sync_rule(key='gpu_hotspot_delta', active_condition=game_context and delta_valid >= 15 and (delta_high >= 15), clear_condition=not game_context or (delta_safe_valid >= 12 and delta_safe >= 12), component='GPU', level='INFO', title='Diferencia hotspot-core elevada', detail='La diferencia hotspot-core estuvo en 25 °C o más en una proporción alta de las últimas 20 muestras.', evidence=[f'Delta actual: {delta:.1f} °C' if _num(delta) else 'Delta actual: N/A', f'Evidencia: {delta_high}/{delta_valid} muestras'], context=context, now=now)
        ft12 = self._recent(12, contexts={'GAME_ACTIVE'})
        bad_ft, valid_ft = self._ratio(ft12, lambda s: s['frametime_ms'] >= 50 if _num(s.get('frametime_ms')) else None)
        good_ft, valid_good_ft = self._ratio(ft12, lambda s: s['frametime_ms'] < 35 if _num(s.get('frametime_ms')) else None)
        ft = sample.get('frametime_ms')
        self._sync_rule(key='game_frametime_high', active_condition=context == 'GAME_ACTIVE' and valid_ft >= 10 and (bad_ft >= 8), clear_condition=context != 'GAME_ACTIVE' or (valid_good_ft >= 8 and good_ft >= 8), component='GAME', level='WARNING', title='Frametime alto sostenido', detail='El frametime estuvo en 50 ms o más en al menos 8 de las últimas 12 muestras válidas de GAME_ACTIVE.', evidence=[f'Frametime actual: {ft} ms' if _num(ft) else 'Frametime: N/A', f"FPS RTSS: {sample.get('fps'):.1f}" if _num(sample.get('fps')) else 'FPS RTSS: N/A', f'Evidencia: {bad_ft}/{valid_ft} muestras'], context=context, now=now)
        return self.snapshot()

    def snapshot(self):
        active = [asdict(copy.deepcopy(event)) for event in self._active.values()]
        severity = {'CRITICAL': 0, 'WARNING': 1, 'INFO': 2}
        active.sort(key=lambda item: (severity.get(item['level'], 9), item['first_seen']))
        history = [asdict(copy.deepcopy(event)) for event in self._history]
        return {'engine': 'Rolling Evidence', 'active': active, 'history': history, 'active_count': len(active), 'history_count': len(history)}

    def overall(self):
        levels = {event.level for event in self._active.values()}
        if 'CRITICAL' in levels:
            return 'CRITICAL'
        if 'WARNING' in levels:
            return 'WARNING'
        if 'INFO' in levels:
            return 'INFO'
        return 'NORMAL'
