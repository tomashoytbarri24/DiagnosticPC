"""Administra las muestras, reglas y resultado congelado de una sesión de diagnóstico."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import json
import math
import os
import statistics
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
SESSION_SECONDS = 120
SAMPLE_INTERVAL_SECONDS = 1.0

@dataclass
class Finding:
    component: str
    status: str
    title: str
    explanation: str
    evidence: list[str]
    rule_source: str

def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = float(value)
        if math.isfinite(value):
            return value
    return None

def _stats(values):
    clean = [_number(v) for v in values]
    clean = [v for v in clean if v is not None]
    if not clean:
        return {'samples': 0, 'min': None, 'max': None, 'avg': None, 'median': None}
    return {'samples': len(clean), 'min': round(min(clean), 3), 'max': round(max(clean), 3), 'avg': round(sum(clean) / len(clean), 3), 'median': round(statistics.median(clean), 3)}

class DiagnosticSession:

    def __init__(self, duration_seconds=SESSION_SECONDS):
        self.duration_seconds = int(duration_seconds)
        self._lock = threading.RLock()
        self._active = False
        self._completed = False
        self._started_monotonic = None
        self._started_wall = None
        self._ended_wall = None
        self._last_sample_monotonic = 0.0
        self._samples = []
        self._result = None

    @property
    def active(self):
        with self._lock:
            return self._active

    @property
    def completed(self):
        with self._lock:
            return self._completed

    @property
    def result(self):
        with self._lock:
            return self._result

    def start(self):
        with self._lock:
            self._samples = []
            self._result = None
            self._active = True
            self._completed = False
            self._started_monotonic = time.monotonic()
            self._started_wall = datetime.now().astimezone().isoformat()
            self._ended_wall = None
            self._last_sample_monotonic = 0.0

    def elapsed_seconds(self):
        with self._lock:
            if self._started_monotonic is None:
                return 0.0
            if self._active:
                return max(0.0, time.monotonic() - self._started_monotonic)
            if self._result:
                return float(self._result.get('duration_seconds', 0))
            return 0.0

    def remaining_seconds(self):
        return max(0, self.duration_seconds - int(self.elapsed_seconds()))

    def should_finish(self):
        return self.active and self.elapsed_seconds() >= self.duration_seconds

    def add_sample(self, telemetry, disks=None):
        now = time.monotonic()
        with self._lock:
            if not self._active:
                return False
            if now - self._last_sample_monotonic < SAMPLE_INTERVAL_SECONDS:
                return False
            self._last_sample_monotonic = now
            cpu = telemetry.get('_cpu') or {}
            gpus = telemetry.get('_gpus') or []
            storage = telemetry.get('_storage_devices') or []
            battery = telemetry.get('_battery')
            sample = {'timestamp': datetime.now().astimezone().isoformat(), 'elapsed_seconds': round(self.elapsed_seconds(), 3), 'cpu_usage_percent': _number(telemetry.get('cpu_usage')), 'cpu_package_temp_c': _number(cpu.get('package_temp_c') or telemetry.get('cpu_temp')), 'cpu_core_max_temp_c': _number(cpu.get('core_max_temp_c')), 'cpu_core_average_temp_c': _number(cpu.get('core_average_temp_c')), 'cpu_distance_to_tjmax_min_c': _number(cpu.get('distance_to_tjmax_min_c')), 'cpu_clock_avg_ghz': _number(cpu.get('clock_avg_ghz') or telemetry.get('cpu_ghz')), 'cpu_package_power_w': _number(cpu.get('package_power_w')), 'ram_usage_percent': _number(telemetry.get('ram_usage')), 'gpus': [], 'storage': [], 'battery': battery.copy() if isinstance(battery, dict) else None}
            for gpu in gpus:
                sample['gpus'].append({'name': gpu.get('name'), 'hardware_type': gpu.get('hardware_type'), 'temperature_c': _number(gpu.get('temperature_c')), 'hotspot_c': _number(gpu.get('hotspot_c')), 'usage_percent': _number(gpu.get('usage_percent')), 'memory_usage_percent': _number(gpu.get('memory_usage_percent')), 'power_w': _number(gpu.get('power_w'))})
            for drive in storage:
                sample['storage'].append({'name': drive.get('name'), 'temperature_c': _number(drive.get('temperature_c')), 'warning_temperature_c': _number(drive.get('warning_temperature_c')), 'critical_temperature_c': _number(drive.get('critical_temperature_c')), 'life_percent': _number(drive.get('life_percent')), 'used_space_percent': _number(drive.get('used_space_percent')), 'power_on_hours': _number(drive.get('power_on_hours'))})
            self._samples.append(sample)
            return True

    def finish(self):
        with self._lock:
            if not self._active:
                return self._result
            self._active = False
            self._completed = True
            self._ended_wall = datetime.now().astimezone().isoformat()
            duration = max(self.duration_seconds, int(round(time.monotonic() - self._started_monotonic)))
            statistics_data = self._build_statistics()
            findings = self._build_findings(statistics_data)
            overall = self._overall_status(findings)
            self._result = {'corepulse_version': '0.6', 'session_valid': duration >= self.duration_seconds, 'required_duration_seconds': self.duration_seconds, 'duration_seconds': duration, 'sample_interval_seconds': SAMPLE_INTERVAL_SECONDS, 'sample_count': len(self._samples), 'started_at': self._started_wall, 'ended_at': self._ended_wall, 'overall_status': overall, 'statistics': statistics_data, 'findings': [asdict(f) for f in findings], 'data_policy': {'missing_values': 'UNAVAILABLE / no evaluable', 'fabricated_sensor_values': False, 'statistics': 'derived only from collected numeric samples'}}
            return self._result

    def _build_statistics(self):
        samples = list(self._samples)
        result = {'cpu': {'usage_percent': _stats([s['cpu_usage_percent'] for s in samples]), 'package_temp_c': _stats([s['cpu_package_temp_c'] for s in samples]), 'core_max_temp_c': _stats([s['cpu_core_max_temp_c'] for s in samples]), 'core_average_temp_c': _stats([s['cpu_core_average_temp_c'] for s in samples]), 'distance_to_tjmax_min_c': _stats([s['cpu_distance_to_tjmax_min_c'] for s in samples]), 'clock_avg_ghz': _stats([s['cpu_clock_avg_ghz'] for s in samples]), 'package_power_w': _stats([s['cpu_package_power_w'] for s in samples]), 'seconds_within_5c_tjmax': 0, 'seconds_within_10c_tjmax': 0}, 'ram': {'usage_percent': _stats([s['ram_usage_percent'] for s in samples]), 'seconds_over_85_percent': 0, 'seconds_over_90_percent': 0, 'seconds_over_95_percent': 0}, 'gpus': {}, 'storage': {}, 'battery': None}
        for s in samples:
            d = s['cpu_distance_to_tjmax_min_c']
            if d is not None:
                if d <= 5:
                    result['cpu']['seconds_within_5c_tjmax'] += 1
                if d <= 10:
                    result['cpu']['seconds_within_10c_tjmax'] += 1
            ram = s['ram_usage_percent']
            if ram is not None:
                if ram >= 85:
                    result['ram']['seconds_over_85_percent'] += 1
                if ram >= 90:
                    result['ram']['seconds_over_90_percent'] += 1
                if ram >= 95:
                    result['ram']['seconds_over_95_percent'] += 1
        gpu_names = []
        storage_names = []
        for s in samples:
            for gpu in s['gpus']:
                name = gpu.get('name')
                if name and name not in gpu_names:
                    gpu_names.append(name)
            for drive in s['storage']:
                name = drive.get('name')
                if name and name not in storage_names:
                    storage_names.append(name)
        for name in gpu_names:
            records = []
            for s in samples:
                records.extend([g for g in s['gpus'] if g.get('name') == name])
            result['gpus'][name] = {'usage_percent': _stats([r['usage_percent'] for r in records]), 'temperature_c': _stats([r['temperature_c'] for r in records]), 'hotspot_c': _stats([r['hotspot_c'] for r in records]), 'memory_usage_percent': _stats([r['memory_usage_percent'] for r in records]), 'power_w': _stats([r['power_w'] for r in records])}
        for name in storage_names:
            records = []
            for s in samples:
                records.extend([d for d in s['storage'] if d.get('name') == name])
            current = records[-1] if records else {}
            warning = current.get('warning_temperature_c')
            critical = current.get('critical_temperature_c')
            seconds_warning = 0
            seconds_critical = 0
            for r in records:
                temp = r['temperature_c']
                if temp is None:
                    continue
                if warning is not None and temp >= warning:
                    seconds_warning += 1
                if critical is not None and temp >= critical:
                    seconds_critical += 1
            result['storage'][name] = {'temperature_c': _stats([r['temperature_c'] for r in records]), 'warning_temperature_c': warning, 'critical_temperature_c': critical, 'seconds_at_or_above_warning': seconds_warning, 'seconds_at_or_above_critical': seconds_critical, 'life_percent': current.get('life_percent'), 'used_space_percent': current.get('used_space_percent'), 'power_on_hours': current.get('power_on_hours')}
        batteries = [s['battery'] for s in samples if isinstance(s.get('battery'), dict)]
        if batteries:
            result['battery'] = batteries[-1]
        return result

    def _build_findings(self, stats):
        findings = []
        cpu = stats['cpu']
        tj = cpu['distance_to_tjmax_min_c']
        if tj['samples'] > 0:
            near5 = cpu['seconds_within_5c_tjmax']
            near10 = cpu['seconds_within_10c_tjmax']
            if near5 >= 30:
                findings.append(Finding('CPU', 'CRITICAL', 'CPU sostenidamente muy cerca de TjMax', 'Durante una parte importante de la sesión el procesador estuvo a 5 °C o menos de su TjMax reportado.', [f'Tiempo ≤5 °C de TjMax: {near5} s', f"Distancia mínima registrada: {tj['min']} °C", f"CPU Package máximo: {cpu['package_temp_c']['max']} °C"], 'CorePulse policy based on hardware-reported Distance to TjMax'))
            elif near10 >= 30:
                findings.append(Finding('CPU', 'WARNING', 'CPU permaneció cerca de TjMax', 'El procesador pasó al menos 30 segundos a 10 °C o menos de su TjMax.', [f'Tiempo ≤10 °C de TjMax: {near10} s', f"Distancia mínima registrada: {tj['min']} °C", f"CPU Package promedio: {cpu['package_temp_c']['avg']} °C"], 'CorePulse policy based on hardware-reported Distance to TjMax'))
            else:
                findings.append(Finding('CPU', 'NORMAL', 'Sin proximidad térmica sostenida a TjMax', 'La sesión no mostró una permanencia prolongada dentro de 10 °C de TjMax.', [f'Tiempo ≤10 °C de TjMax: {near10} s', f"CPU Package promedio: {cpu['package_temp_c']['avg']} °C", f"CPU Package máximo: {cpu['package_temp_c']['max']} °C"], 'CorePulse policy based on hardware-reported Distance to TjMax'))
        else:
            findings.append(Finding('CPU', 'NO_EVALUABLE', 'Temperatura CPU no evaluable', 'No hubo suficientes muestras de Distance to TjMax para evaluar la condición térmica de CPU.', [], 'Availability rule'))
        ram = stats['ram']
        if ram['usage_percent']['samples'] > 0:
            valid = int(ram['usage_percent']['samples'] or 0)
            over85 = int(ram.get('seconds_over_85_percent') or 0)
            over90 = int(ram.get('seconds_over_90_percent') or 0)
            over95 = int(ram.get('seconds_over_95_percent') or 0)
            # Política CorePulse de presión de memoria adaptada a diagnósticos de 30-90 s.
            # No representa un límite físico del fabricante: describe presión sostenida de uso.
            extreme_required = max(12, min(30, int(round(valid * 0.40))))
            high_required = max(15, min(35, int(round(valid * 0.50))))
            elevated_required = max(18, min(45, int(round(valid * 0.60))))
            if over95 >= extreme_required:
                findings.append(Finding('RAM', 'WARNING', 'Presión extrema sostenida de memoria', 'La RAM permaneció en 95% o más durante una parte material de la sesión. Esto describe presión de memoria y posible paginación, no un fallo físico del módulo.', [f'Tiempo ≥95%: {over95} s', f"Uso promedio: {ram['usage_percent']['avg']}%", f"Uso máximo: {ram['usage_percent']['max']}%"], 'CorePulse RAM pressure policy: >=95% sustained'))
            elif over90 >= high_required:
                findings.append(Finding('RAM', 'WARNING', 'Uso alto sostenido de memoria', 'La RAM permaneció en 90% o más durante una parte importante de la sesión. CorePulse recomienda identificar la carga responsable y comprobar si la presión persiste en el uso habitual.', [f'Tiempo ≥90%: {over90} s', f"Uso promedio: {ram['usage_percent']['avg']}%", f"Uso máximo: {ram['usage_percent']['max']}%"], 'CorePulse RAM pressure policy: >=90% sustained'))
            elif over85 >= elevated_required:
                findings.append(Finding('RAM', 'INFO', 'Uso de RAM elevado pero no crítico', 'Se observó uso de RAM en 85% o más de forma sostenida, pero sin alcanzar el criterio de advertencia de CorePulse.', [f'Tiempo ≥85%: {over85} s', f"Uso promedio: {ram['usage_percent']['avg']}%", f"Uso máximo: {ram['usage_percent']['max']}%"], 'CorePulse RAM advisory policy: >=85% sustained'))
            else:
                findings.append(Finding('RAM', 'NORMAL', 'Sin presión sostenida de RAM', 'La sesión no mostró presión de memoria suficiente para activar una advertencia.', [f"Uso promedio: {ram['usage_percent']['avg']}%", f"Uso máximo: {ram['usage_percent']['max']}%"], 'CorePulse RAM pressure policy'))
        else:
            findings.append(Finding('RAM', 'NO_EVALUABLE', 'RAM no evaluable', 'No se recopilaron muestras válidas de uso de RAM.', [], 'Availability rule'))
        for name, drive in stats['storage'].items():
            used = _number(drive.get('used_space_percent'))
            if used is not None:
                free = max(0.0, 100.0 - used)
                if used >= 95.0:
                    findings.append(Finding(f'STORAGE:{name}', 'WARNING', 'Espacio libre críticamente reducido', 'La unidad alcanzó 95% o más de ocupación. Esta es una política de capacidad de CorePulse; no implica por sí sola degradación SMART.', [f'Espacio usado: {round(used, 1)}%', f'Espacio libre estimado por porcentaje: {round(free, 1)}%'], 'CorePulse storage capacity policy: >=95% used'))
                elif used >= 90.0:
                    findings.append(Finding(f'STORAGE:{name}', 'WARNING', 'Poco espacio libre en almacenamiento', 'La unidad alcanzó 90% o más de ocupación. CorePulse recomienda recuperar margen para actualizaciones, temporales y paginación.', [f'Espacio usado: {round(used, 1)}%', f'Espacio libre estimado por porcentaje: {round(free, 1)}%'], 'CorePulse storage capacity policy: >=90% used'))
                elif used >= 85.0:
                    findings.append(Finding(f'STORAGE:{name}', 'INFO', 'Margen de almacenamiento reducido', 'La unidad supera 85% de ocupación, pero todavía no alcanza el criterio de advertencia de CorePulse.', [f'Espacio usado: {round(used, 1)}%', f'Espacio libre estimado por porcentaje: {round(free, 1)}%'], 'CorePulse storage capacity advisory: >=85% used'))
            if drive['temperature_c']['samples'] == 0:
                findings.append(Finding(f'STORAGE:{name}', 'NO_EVALUABLE', 'Temperatura de almacenamiento no evaluable', 'El dispositivo no entregó temperatura actual válida durante la sesión.', [], 'Availability rule'))
                continue
            if drive['seconds_at_or_above_critical'] > 0:
                status = 'CRITICAL'
                title = 'Almacenamiento alcanzó el umbral crítico reportado'
            elif drive['seconds_at_or_above_warning'] >= 30:
                status = 'WARNING'
                title = 'Almacenamiento permaneció sobre su umbral de advertencia'
            else:
                status = 'NORMAL'
                title = 'Temperatura de almacenamiento dentro de sus umbrales reportados'
            evidence = [f"Temperatura promedio: {drive['temperature_c']['avg']} °C", f"Temperatura máxima: {drive['temperature_c']['max']} °C"]
            if drive['warning_temperature_c'] is not None:
                evidence.append(f"Umbral warning del dispositivo: {drive['warning_temperature_c']} °C")
            if drive['critical_temperature_c'] is not None:
                evidence.append(f"Umbral crítico del dispositivo: {drive['critical_temperature_c']} °C")
            if drive['life_percent'] is not None:
                evidence.append(f"Life reportado: {drive['life_percent']}%")
            findings.append(Finding(f'STORAGE:{name}', status, title, 'La clasificación térmica usa los umbrales que el propio dispositivo/proveedor reporta.', evidence, 'Device-reported storage thresholds'))
        for name, gpu in stats['gpus'].items():
            if gpu['temperature_c']['samples'] == 0:
                findings.append(Finding(f'GPU:{name}', 'NO_EVALUABLE', 'Temperatura GPU no evaluable', 'No se obtuvo temperatura GPU válida durante la sesión.', [], 'Availability rule'))
            else:
                findings.append(Finding(f'GPU:{name}', 'INFO', 'Telemetría GPU recopilada', 'CorePulse conserva temperatura, hotspot y uso, pero V0.6 no declara salud térmica GPU sin un límite específico del modelo/proveedor.', [f"Temperatura promedio: {gpu['temperature_c']['avg']} °C", f"Temperatura máxima: {gpu['temperature_c']['max']} °C", f"Hotspot máximo: {gpu['hotspot_c']['max']} °C", f"Uso máximo: {gpu['usage_percent']['max']}%"], 'Evidence-only GPU rule'))
        battery = stats.get('battery')
        if battery:
            degradation = _number(battery.get('degradation_percent'))
            if degradation is not None:
                findings.append(Finding('BATTERY', 'INFO', 'Desgaste de batería reportado', 'Se registra la degradación que expone el proveedor. V0.6 no la interpreta como fallo automático.', [f'Degradación reportada: {degradation}%', f"Capacidad de diseño: {battery.get('designed_capacity_mwh')} mWh", f"Capacidad carga completa: {battery.get('full_charge_capacity_mwh')} mWh"], 'Provider-reported battery degradation'))
        return findings

    @staticmethod
    def _overall_status(findings):
        statuses = {f.status for f in findings}
        if 'CRITICAL' in statuses:
            return 'CRITICAL'
        if 'WARNING' in statuses:
            return 'WARNING'
        evaluable = [f for f in findings if f.status not in {'INFO', 'NO_EVALUABLE'}]
        if evaluable and all((f.status == 'NORMAL' for f in evaluable)):
            return 'NORMAL'
        return 'NO_EVALUABLE'

    def save_json(self, path=None):
        with self._lock:
            if self._result is None:
                return None
            if path is None:
                output_root = Path(os.getenv('LOCALAPPDATA', '.')) / 'CorePulse' / 'diagnostics'
                output_root.mkdir(parents=True, exist_ok=True)
                path = output_root / f'CorePulse_Diagnostic_{datetime.now():%Y%m%d_%H%M%S}.json'
            else:
                path = Path(path)
                path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._result, indent=2, ensure_ascii=False), encoding='utf-8')
            return str(path)
