"""Detector de throttling basado en evidencia observable y sensores explícitos."""
from __future__ import annotations

import time
from collections import deque
from typing import Any, Dict


def _num(v):
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


class ThermalThrottlingDetector:
    def __init__(self, max_samples: int = 60):
        self.samples = deque(maxlen=max(12, int(max_samples)))

    def add_sample(self, telemetry: Dict[str, Any] | None):
        t = telemetry if isinstance(telemetry, dict) else {}
        cpu = t.get('_cpu') if isinstance(t.get('_cpu'), dict) else {}
        gpus = t.get('_gpus') if isinstance(t.get('_gpus'), list) else []
        sample = {
            'ts': time.time(),
            'cpu_usage': _num(t.get('cpu_usage')),
            'cpu_temp': _num(t.get('cpu_temp')),
            'cpu_clock': _num(t.get('cpu_ghz')) or _num(cpu.get('clock_avg_ghz')),
            'cpu_max_observed': _num(cpu.get('clock_max_ghz')),
            'cpu_power': _num(cpu.get('package_power_w')),
            'cpu_tj_distance': _num(cpu.get('distance_to_tjmax_min_c')),
            'cpu_sensors': cpu.get('sensors') if isinstance(cpu.get('sensors'), list) else [],
            'gpus': gpus,
        }
        self.samples.append(sample)
        return self.evaluate()

    @staticmethod
    def _explicit_reason(sensors):
        for s in sensors or []:
            if not isinstance(s, dict):
                continue
            name = str(s.get('name') or s.get('sensor_name') or '').lower()
            value = _num(s.get('value'))
            if value is None or value <= 0:
                continue
            if 'thermal thrott' in name or 'thermal limit' in name:
                return 'THERMAL', str(s.get('name') or s.get('sensor_name'))
            if 'power limit' in name or 'power thrott' in name:
                return 'POWER', str(s.get('name') or s.get('sensor_name'))
        return None, None

    def evaluate(self):
        if not self.samples:
            return {'cpu': {'state': 'N/A'}, 'gpu': {'state': 'N/A'}, 'policy': 'EVIDENCE_FIRST'}
        cur = self.samples[-1]
        reason, sensor = self._explicit_reason(cur.get('cpu_sensors'))
        cpu = {'state': 'NO_EVIDENCE', 'reason': None, 'confidence': 'LOW', 'evidence': [], 'explicit_sensor': sensor}
        if reason:
            cpu.update(state='CONFIRMED', reason=reason, confidence='HIGH')
            cpu['evidence'].append(f'Sensor explícito: {sensor}')
        else:
            usage = cur.get('cpu_usage')
            temp = cur.get('cpu_temp')
            dist = cur.get('cpu_tj_distance')
            clock = cur.get('cpu_clock')
            recent_clocks = [s.get('cpu_clock') for s in list(self.samples)[-15:] if s.get('cpu_clock') is not None]
            peak = max(recent_clocks) if recent_clocks else cur.get('cpu_max_observed')
            clock_drop = (clock is not None and peak and peak > 0 and clock < peak * 0.78)
            hot = (dist is not None and dist <= 5.0) or (temp is not None and temp >= 95.0)
            warm = (dist is not None and dist <= 10.0) or (temp is not None and temp >= 90.0)
            loaded = usage is not None and usage >= 65.0
            if hot and loaded and clock_drop:
                cpu.update(state='SUSPECTED', reason='THERMAL', confidence='MEDIUM')
                cpu['evidence'] += ['Carga elevada', 'Margen térmico crítico', 'Caída de frecuencia respecto al pico reciente']
            elif warm and loaded:
                cpu.update(state='WATCHING', reason='THERMAL_HEADROOM', confidence='MEDIUM')
                cpu['evidence'] += ['Carga elevada', 'Margen térmico reducido']
            elif loaded and clock_drop and not hot:
                cpu.update(state='SUSPECTED', reason='POWER_OR_PLATFORM_LIMIT', confidence='LOW')
                cpu['evidence'] += ['Carga elevada', 'Frecuencia reducida sin evidencia térmica suficiente']

        gpu = {'state': 'NO_EVIDENCE', 'reason': None, 'confidence': 'LOW', 'devices': []}
        recent = list(self.samples)[-15:]
        for idx, g in enumerate(cur.get('gpus') or []):
            if not isinstance(g, dict):
                continue
            sensors = g.get('sensors') if isinstance(g.get('sensors'), list) else []
            greason, gsensor = self._explicit_reason(sensors)
            name = g.get('name') or g.get('hardware')
            item = {'index': idx, 'name': name, 'state': 'NO_EVIDENCE', 'reason': None, 'confidence': 'LOW', 'explicit_sensor': gsensor, 'evidence': []}
            if greason:
                item.update(state='CONFIRMED', reason=greason, confidence='HIGH')
                item['evidence'].append(f'Sensor explícito: {gsensor}')
            else:
                usage = _num(g.get('usage_percent')); temp = _num(g.get('temperature_c')); hotspot = _num(g.get('hotspot_c')); clock = _num(g.get('core_clock_mhz'))
                clocks=[]
                for smp in recent:
                    for oldg in smp.get('gpus') or []:
                        if isinstance(oldg,dict) and (oldg.get('name') or oldg.get('hardware')) == name:
                            val=_num(oldg.get('core_clock_mhz'))
                            if val is not None: clocks.append(val)
                peak=max(clocks) if clocks else None
                drop=clock is not None and peak and peak>0 and clock < peak*0.78
                hot=(hotspot is not None and hotspot>=100) or (temp is not None and temp>=88)
                loaded=usage is not None and usage>=75
                if hot and loaded and drop:
                    item.update(state='SUSPECTED',reason='THERMAL',confidence='MEDIUM')
                    item['evidence'] += ['Carga GPU elevada','Temperatura alta','Caída de core clock respecto al pico reciente']
                elif loaded and drop:
                    item.update(state='SUSPECTED',reason='POWER_OR_PLATFORM_LIMIT',confidence='LOW')
                    item['evidence'] += ['Carga GPU elevada','Core clock reducido sin sensor de causa explícito']
            gpu['devices'].append(item)
        if any(d.get('state') == 'CONFIRMED' for d in gpu['devices']):
            gpu.update(state='CONFIRMED', confidence='HIGH')
        elif any(d.get('state') == 'SUSPECTED' for d in gpu['devices']):
            gpu.update(state='SUSPECTED', confidence='MEDIUM')
        return {'cpu': cpu, 'gpu': gpu, 'policy': 'CONFIRMED_ONLY_WITH_EXPLICIT_SENSOR_OTHERWISE_SUSPECTED'}
