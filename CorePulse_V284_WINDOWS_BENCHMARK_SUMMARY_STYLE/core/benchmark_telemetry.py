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


def first_number(*values):
    for value in values:
        parsed = number(value)
        if parsed is not None:
            return parsed
    return None


def peak(states, available):
    if not available:
        return {'state': 'N/A', 'evidence': []}
    ranks = {'N/A': 0, 'NO_EVIDENCE': 1, 'WATCHING': 2, 'SUSPECTED': 3, 'CONFIRMED': 4}
    return copy.deepcopy(max(states, key=lambda s: ranks.get(s.get('state'), 0),
                             default={'state': 'N/A', 'evidence': []}))



def _gpu_reported_temperature_limit(gpu, *, hotspot=False):
    """Devuelve un límite térmico sólo si existe como sensor real del adaptador."""
    if not isinstance(gpu, dict):
        return None
    rows = gpu.get('sensors') if isinstance(gpu.get('sensors'), list) else []
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get('name') or row.get('sensor_name') or '').casefold()
        sensor_type = str(row.get('type') or row.get('sensor_type') or '').casefold()
        value = number(row.get('value'))
        if value is None or not (20.0 <= value <= 150.0):
            continue
        is_limit = (('limit' in name or 'critical' in name) and
                    ('temp' in name or 'thermal' in name or sensor_type == 'temperature'))
        if not is_limit:
            continue
        is_hotspot = 'hot' in name or 'junction' in name
        if hotspot == is_hotspot:
            candidates.append(value)
    return candidates[0] if candidates else None


def _observed_excursion(rows, value_getter, threshold):
    """Resume sólo lecturas observadas; no interpola tiempo entre muestras."""
    samples = []
    max_span = 0.0
    streak_start = None
    streak_last = None
    for row in rows:
        value = number(value_getter(row))
        ts = number(row.get('ts'))
        if value is not None and value >= threshold:
            samples.append({'ts': ts, 'value': value})
            if ts is not None:
                if streak_start is None:
                    streak_start = ts
                streak_last = ts
                max_span = max(max_span, max(0.0, streak_last - streak_start))
        else:
            streak_start = None
            streak_last = None
    return {
        'threshold_c': float(threshold),
        'sample_count_at_or_above': len(samples),
        'peak_c': max((item['value'] for item in samples), default=None),
        'first_observed_timestamp': next((item['ts'] for item in samples if item['ts'] is not None), None),
        'last_observed_timestamp': next((item['ts'] for item in reversed(samples) if item['ts'] is not None), None),
        'max_consecutive_observed_span_s': round(max_span, 3) if samples else None,
        'duration_policy': 'TIMESTAMP_SPAN_BETWEEN_CONSECUTIVE_REAL_SAMPLES_NO_INTERPOLATION',
    }


def _observed_at_or_below(rows, value_getter, threshold):
    """Audita el gatillo térmico real sin inferir muestras intermedias."""
    samples = []
    max_span = 0.0
    max_count = 0
    streak_start = None
    streak_last = None
    streak_count = 0
    for row in rows:
        value = number(value_getter(row))
        ts = number(row.get('ts'))
        if value is not None and value <= threshold:
            samples.append({'ts': ts, 'value': value})
            streak_count += 1
            max_count = max(max_count, streak_count)
            if ts is not None:
                if streak_start is None:
                    streak_start = ts
                streak_last = ts
                max_span = max(max_span, max(0.0, streak_last - streak_start))
        else:
            streak_start = None
            streak_last = None
            streak_count = 0
    return {
        'threshold_c': float(threshold),
        'sample_count_at_or_below': len(samples),
        'minimum_c': min((item['value'] for item in samples), default=None),
        'max_consecutive_sample_count': max_count,
        'max_consecutive_observed_span_s': round(max_span, 3) if samples else None,
        'trigger_samples_required': 3,
        'trigger_observed': bool(max_count >= 3),
        'duration_policy': 'TIMESTAMP_SPAN_BETWEEN_CONSECUTIVE_REAL_SAMPLES_NO_INTERPOLATION',
    }

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

    def __init__(self, sampler=None, storage_inventory=None, active_component=None):
        self.sampler = sampler
        self.rows = []
        self.stop_reason = None
        self.last_sample = 0.0
        self.detector = ThermalThrottlingDetector(max_samples=120)
        self.sampler_errors = []
        self.storage_inventory = storage_inventory or []
        self.active_component = str(active_component or '').strip().lower() or None
        self.safety_warnings = []
        self._cpu_safety_hits = 0
        self._gpu_safety_hits = 0

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
               'cpu_tjmax_distance': first_number(cpu.get('distance_to_tjmax_min_c'), raw.get('cpu_tjmax_distance'), raw.get('distance_to_tjmax_min_c')),
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
        # Seguridad térmica del BENCHMARK: registrar temperaturas altas no equivale
        # a abortar. En particular, un benchmark GPU no debe morir sólo porque el CPU
        # toque 96-97 °C en un portátil cuyo TjMax real puede estar en ~100 °C.
        #
        # Sólo detenemos ante evidencia sostenida de margen térmico prácticamente nulo
        # (sensor de distancia a TjMax) o ante un fallback extremo cuando ese sensor no
        # existe. Las temperaturas siguen quedando en la evidencia aunque no detengan.
        gpu_temps = [number(g.get('temperature_c')) for g in row['gpus'] if isinstance(g, dict)]
        gpu_temps.append(number(raw.get('gpu_temp')))
        gpu_temp = max((v for v in gpu_temps if v is not None), default=None)
        cpu_temp = row.get('cpu_temp')
        cpu_distance = row.get('cpu_tjmax_distance')

        if cpu_temp is not None and cpu_temp >= 95.0:
            warning = f'CPU caliente durante benchmark: {cpu_temp:.1f} °C'
            if warning not in self.safety_warnings:
                self.safety_warnings.append(warning)
        if gpu_temp is not None and gpu_temp >= 88.0:
            warning = f'GPU caliente durante benchmark: {gpu_temp:.1f} °C'
            if warning not in self.safety_warnings:
                self.safety_warnings.append(warning)

        # CPU: si tenemos distancia REAL a TjMax, esa es la autoridad. Requiere
        # 3 muestras consecutivas <= 1.0 °C. Si no existe, el fallback es 105 °C,
        # también sostenido, para no inventar un TjMax fijo de 96 °C.
        if cpu_distance is not None:
            self._cpu_safety_hits = self._cpu_safety_hits + 1 if cpu_distance <= 1.0 else 0
        elif cpu_temp is not None:
            self._cpu_safety_hits = self._cpu_safety_hits + 1 if cpu_temp >= 105.0 else 0
        else:
            self._cpu_safety_hits = 0
        if self._cpu_safety_hits >= 3:
            if cpu_distance is not None:
                self.stop_reason = f'Seguridad térmica: CPU permaneció a {cpu_distance:.1f} °C o menos de TjMax'
            else:
                self.stop_reason = f'Seguridad térmica: CPU permaneció en {cpu_temp:.1f} °C sin TjMax disponible'

        # GPU: un límite REAL expuesto por el dispositivo tiene prioridad como
        # evidencia adicional. El fallback de 95 °C se conserva para no relajar la
        # protección cuando el driver no publica ningún límite. Requerimos 3
        # muestras consecutivas igual que antes para evitar abortos por un pico único.
        gpu_limit_reason = None
        for gpu in row['gpus']:
            if not isinstance(gpu, dict):
                continue
            core_temp = number(gpu.get('temperature_c'))
            hotspot_temp = number(gpu.get('hotspot_c'))
            core_limit = _gpu_reported_temperature_limit(gpu, hotspot=False)
            hotspot_limit = _gpu_reported_temperature_limit(gpu, hotspot=True)
            if core_temp is not None and core_limit is not None and core_temp >= core_limit:
                gpu_limit_reason = f'GPU alcanzó límite reportado ({core_temp:.1f}/{core_limit:.1f} °C)'
                break
            if hotspot_temp is not None and hotspot_limit is not None and hotspot_temp >= hotspot_limit:
                gpu_limit_reason = f'GPU hotspot alcanzó límite reportado ({hotspot_temp:.1f}/{hotspot_limit:.1f} °C)'
                break
        gpu_extreme = gpu_temp is not None and gpu_temp >= 95.0
        self._gpu_safety_hits = self._gpu_safety_hits + 1 if (gpu_limit_reason or gpu_extreme) else 0
        if self._gpu_safety_hits >= 3 and not self.stop_reason:
            self.stop_reason = (
                f'Seguridad térmica: {gpu_limit_reason}' if gpu_limit_reason
                else f'Seguridad térmica: GPU permaneció en {gpu_temp:.1f} °C'
            )

    def summary(self, renderer=None, path_root=None):
        rows = self.rows
        during = [r for r in rows if not r['boundary']]
        result = {'sample_count': len(rows), 'during_sample_count': len(during),
                  'sampler_errors': list(self.sampler_errors), 'safety_stop': self.stop_reason,
                  'safety_warnings': list(self.safety_warnings),
                  'active_component': self.active_component,
                  'samples': copy.deepcopy(rows)}
        for key in ('cpu_usage', 'cpu_temp', 'cpu_ghz', 'ram_usage'):
            result[key] = stats(r.get(key) for r in (during or rows))
        result['cpu_tjmax_distance'] = stats(r.get('cpu_tjmax_distance') for r in (during or rows))
        matched = [gpu_for_renderer(r['gpus'], renderer) for r in during]
        for metric, source in (('gpu_usage', 'usage_percent'), ('gpu_temp', 'temperature_c'),
                               ('gpu_clock_mhz', 'core_clock_mhz'), ('gpu_hotspot', 'hotspot_c')):
            result[metric] = stats(g.get(source) for g in matched)
        result['gpu_sensor_match'] = any(matched)
        result['gpu_name'] = renderer if any(matched) else None

        cpu_rows = during or rows
        cpu_excursion = _observed_excursion(cpu_rows, lambda row: row.get('cpu_temp'), 95.0)
        matched_rows = [
            dict(row, _matched_gpu=gpu_for_renderer(row.get('gpus') or [], renderer))
            for row in during
        ]
        gpu_excursion = _observed_excursion(
            matched_rows, lambda row: (row.get('_matched_gpu') or {}).get('temperature_c'), 88.0
        )
        core_limits = [
            _gpu_reported_temperature_limit(row.get('_matched_gpu'), hotspot=False)
            for row in matched_rows
        ]
        hotspot_limits = [
            _gpu_reported_temperature_limit(row.get('_matched_gpu'), hotspot=True)
            for row in matched_rows
        ]
        core_limits = [value for value in core_limits if value is not None]
        hotspot_limits = [value for value in hotspot_limits if value is not None]
        core_margins = []
        hotspot_margins = []
        for row in matched_rows:
            gpu = row.get('_matched_gpu') or {}
            core_temp = number(gpu.get('temperature_c'))
            hot_temp = number(gpu.get('hotspot_c'))
            core_limit = _gpu_reported_temperature_limit(gpu, hotspot=False)
            hot_limit = _gpu_reported_temperature_limit(gpu, hotspot=True)
            if core_temp is not None and core_limit is not None:
                core_margins.append(core_limit - core_temp)
            if hot_temp is not None and hot_limit is not None:
                hotspot_margins.append(hot_limit - hot_temp)
        tjmax_stats = result['cpu_tjmax_distance']
        cpu_safety_observation = _observed_at_or_below(
            cpu_rows, lambda row: row.get('cpu_tjmax_distance'), 1.0
        )
        result['thermal_audit'] = {
            'policy': 'REAL_OR_NA_OBSERVED_SAMPLES_ONLY',
            'sampling_note': 'Los tramos son separación temporal entre muestras reales consecutivas; no se interpola el estado entre lecturas.',
            'cpu': {
                'peak_c': result['cpu_temp'].get('max'),
                'warning_reference_c': 95.0,
                'warning_observation': cpu_excursion,
                'tjmax_distance_c': tjmax_stats,
                'minimum_tjmax_distance_c': tjmax_stats.get('min'),
                'safety_threshold_distance_c': 1.0,
                'safety_observation': cpu_safety_observation,
                'safety_authority': 'REAL_TJMAX_DISTANCE' if tjmax_stats.get('samples') else 'ABSOLUTE_FALLBACK_105C_NO_TJMAX',
                'safety_stop_reason': self.stop_reason if self.stop_reason and 'CPU' in self.stop_reason else None,
            },
            'gpu': {
                'name': renderer if any(matched) else None,
                'peak_c': result['gpu_temp'].get('max'),
                'hotspot_peak_c': result['gpu_hotspot'].get('max'),
                'warning_reference_c': 88.0,
                'warning_observation': gpu_excursion,
                'reported_core_temp_limit_c': core_limits[-1] if core_limits else None,
                'reported_hotspot_limit_c': hotspot_limits[-1] if hotspot_limits else None,
                'minimum_margin_to_reported_core_limit_c': min(core_margins) if core_margins else None,
                'minimum_margin_to_reported_hotspot_limit_c': min(hotspot_margins) if hotspot_margins else None,
                'safety_stop_reason': self.stop_reason if self.stop_reason and 'GPU' in self.stop_reason else None,
            },
        }
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
