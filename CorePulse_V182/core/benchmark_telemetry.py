"""Observación durante el benchmark existente; no genera ninguna carga adicional."""
from __future__ import annotations

import copy
import ntpath
import re
import time

from core.diagnostic_evidence import number, gpu_for_renderer
from core.thermal_throttling import ThermalThrottlingDetector


def stats(values):
    values = [n for v in values if (n := number(v)) is not None]
    return {'samples': len(values), 'initial': values[0] if values else None,
            'min': min(values) if values else None, 'max': max(values) if values else None,
            'avg': sum(values) / len(values) if values else None}


def peak(states, available):
    if not available:
        return {'state': 'N/A', 'evidence': []}
    ranks = {'N/A': 0, 'NO_EVIDENCE': 1, 'WATCHING': 2, 'SUSPECTED': 3, 'CONFIRMED': 4}
    return copy.deepcopy(max(states, key=lambda s: ranks.get(s.get('state'), 0),
                             default={'state': 'N/A', 'evidence': []}))


def same_volume(mount, target):
    def canonical(value):
        text = str(value).strip()
        if len(text) == 2 and text[1] == ':':
            text += '\\'
        return ntpath.normcase(ntpath.normpath(text))
    return bool(mount and target and canonical(mount) == canonical(target))


class BenchmarkTelemetry:
    """Muestreo cooperativo desde progreso/stop_check; sin hilos residuales.

    Mantiene los límites ya usados en V160: CPU 96 °C y GPU 92 °C.
    La GPU del benchmark se identifica por renderer; otro adaptador nunca
    aporta sus temperaturas, frecuencias ni throttling a esa medición.
    """

    def __init__(self, sampler=None, storage_inventory=None):
        self.sampler = sampler
        self.rows = []
        self.stop_reason = None
        self.last_sample = 0.0
        self.detector = ThermalThrottlingDetector(max_samples=120)
        self.sampler_errors = []
        self.storage_inventory = storage_inventory or []

    def sample(self, *, force=False, boundary=False):
        now = time.monotonic()
        if not force and now - self.last_sample < .45:
            return
        self.last_sample = now
        if not callable(self.sampler):
            return
        try:
            raw = copy.deepcopy(self.sampler() or {})
            if not isinstance(raw, dict):
                return
        except Exception as exc:
            message = f'{type(exc).__name__}: {exc}'
            if message not in self.sampler_errors:
                self.sampler_errors.append(message)
            return
        cpu = raw.get('_cpu') if isinstance(raw.get('_cpu'), dict) else {}
        def cpu_value(top, nested):
            value = number(raw.get(top))
            return value if value is not None else number(cpu.get(nested))
        row = {'ts': time.time(), 'boundary': boundary,
               'cpu_usage': cpu_value('cpu_usage', 'usage_percent'),
               'cpu_temp': cpu_value('cpu_temp', 'package_temp_c'),
               'cpu_ghz': cpu_value('cpu_ghz', 'clock_avg_ghz'),
               'ram_usage': number(raw.get('ram_usage')),
               'gpus': raw.get('_gpus') or [], 'storage': copy.deepcopy(raw.get('_storage_devices') or []),
               'source_timestamp': raw.get('_snapshot_timestamp')}
        # La caché inicial aporta identidad/volumen, nunca temperaturas antiguas.
        for disk in row['storage']:
            name = str(disk.get('name') or disk.get('model') or '').strip().casefold()
            candidates = [d for d in self.storage_inventory
                          if name and str(d.get('name') or d.get('model') or '').strip().casefold() == name]
            peers = [d for d in row['storage']
                     if str(d.get('name') or d.get('model') or '').strip().casefold() == name]
            if not disk.get('mount_points') and len(candidates) == len(peers) == 1:
                disk['mount_points'] = candidates[0].get('mount_points')
        raw.update({key: row[key] for key in ('cpu_usage', 'cpu_temp', 'cpu_ghz')})
        row['throttling'] = self.detector.add_sample(raw)
        self.rows.append(row)
        # Todos los adaptadores participan en seguridad, sólo el renderer en evidencia GPU.
        gpu_temps = [number(g.get('temperature_c')) for g in row['gpus'] if isinstance(g, dict)]
        gpu_temps.append(number(raw.get('gpu_temp')))
        gpu_temp = max((v for v in gpu_temps if v is not None), default=None)
        if row['cpu_temp'] is not None and row['cpu_temp'] >= 96.0:
            self.stop_reason = f"Seguridad térmica: CPU alcanzó {row['cpu_temp']:.1f} °C"
        elif gpu_temp is not None and gpu_temp >= 92.0:
            self.stop_reason = f'Seguridad térmica: GPU alcanzó {gpu_temp:.1f} °C'

    def summary(self, renderer=None, path_root=None):
        rows = self.rows
        during = [r for r in rows if not r['boundary']]
        result = {'sample_count': len(rows), 'during_sample_count': len(during),
                  'sampler_errors': list(self.sampler_errors), 'safety_stop': self.stop_reason,
                  'samples': copy.deepcopy(rows)}
        for key in ('cpu_usage', 'cpu_temp', 'cpu_ghz', 'ram_usage'):
            result[key] = stats(r.get(key) for r in (during or rows))
        matched = [gpu_for_renderer(r['gpus'], renderer) for r in during]
        for metric, source in (('gpu_usage', 'usage_percent'), ('gpu_temp', 'temperature_c'),
                               ('gpu_clock_mhz', 'core_clock_mhz')):
            result[metric] = stats(g.get(source) for g in matched)
        result['gpu_sensor_match'] = any(matched)
        result['gpu_name'] = renderer if any(matched) else None
        cpu_states = [r['throttling']['cpu'] for r in during]
        gpu_states = [d for r in during for d in r['throttling']['gpu'].get('devices', [])
                      if renderer and str(d.get('name') or '').strip().casefold() == str(renderer).strip().casefold()]
        cpu_available = all(result[k]['samples'] for k in ('cpu_temp', 'cpu_usage', 'cpu_ghz')) or any(s.get('explicit_sensor') or s.get('state') in {'WATCHING', 'SUSPECTED', 'CONFIRMED'} for s in cpu_states)
        gpu_available = all(result[k]['samples'] for k in ('gpu_temp', 'gpu_usage', 'gpu_clock_mhz')) or any(s.get('explicit_sensor') for s in gpu_states)
        result['throttling'] = {'cpu': peak(cpu_states, cpu_available),
                                'gpu': peak(gpu_states, gpu_available)}
        # No usar la temperatura de otro disco cuando el volumen no se puede enlazar.
        disk_values, identities = [], []
        for row in rows:
            candidates = []
            for disk in row['storage']:
                mounts = disk.get('mount_points') or []
                if isinstance(mounts, str):
                    mounts = re.split(r'[,;\s]+', mounts.strip())
                if any(same_volume(m, path_root) for m in mounts):
                    candidates.append(disk)
            if len(candidates) == 1:
                disk = candidates[0]
                disk_values.append(disk.get('temperature_c'))
                identities.append(str(disk.get('name') or disk.get('model') or 'N/A'))
        result['storage_temperature'] = stats(disk_values)
        result['storage_names'] = sorted(set(identities))
        result['storage_volume'] = path_root
        return result
