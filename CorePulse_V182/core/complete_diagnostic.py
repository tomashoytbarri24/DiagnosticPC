"""Orquestador del Diagnóstico Completo de CorePulse.

V162 conserva el flujo V161 y unifica la metodología del benchmark GPU entre el módulo Benchmark y Diagnóstico:
- observación pasiva en escritorio (AdaptiveDiagnosticSession);
- estado real de Windows/hardware;
- telemetría observada durante el benchmark, sin carga adicional;
- benchmark (rendimiento medido, sin ranking externo).

Las reparaciones siguen siendo acciones explícitas del usuario y no se ejecutan aquí.
"""
from __future__ import annotations

import copy
import concurrent.futures
import hashlib
import json
import math
import os
import platform
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from core.battery_health import collect_battery_health
from core.benchmark_engine import benchmark_gpu, run_benchmark_suite
from core.audio_test import automatic_audio_probe
from core.runtime_paths import diagnostics_dir
from core.thermal_throttling import ThermalThrottlingDetector
from core.version import VERSION_LABEL
from core.cancellable_process import cancellation_scope
from core.diagnostic_lifecycle import is_finalized_result
from core.diagnostic_evidence import storage_snapshot, active_gpu, gpu_for_renderer, physical_health
if platform.system() == 'Windows':
    from core.windows_health import analyze_crashes, analyze_drivers, analyze_services, analyze_startup
else:
    analyze_crashes = analyze_drivers = analyze_services = analyze_startup = None

ProgressCallback = Optional[Callable[[float, str, str], None]]
TelemetrySampler = Optional[Callable[[], Dict[str, Any]]]
CancelCheck = Optional[Callable[[], bool]]


def _num(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def _emit(callback: ProgressCallback, fraction: float, stage: str, detail: str = ''):
    if not callable(callback):
        return
    try:
        callback(max(0.0, min(1.0, float(fraction))), str(stage), str(detail or ''))
    except Exception:
        pass


def _telemetry_row(telemetry: Dict[str, Any] | None) -> Dict[str, Any]:
    t = telemetry if isinstance(telemetry, dict) else {}
    cpu = t.get('_cpu') if isinstance(t.get('_cpu'), dict) else {}
    gpus = t.get('_gpus') if isinstance(t.get('_gpus'), list) else []
    gpu = active_gpu(gpus)
    return {
        'ts': time.time(),
        'cpu_usage': _num(t.get('cpu_usage')),
        'cpu_temp': _num(t.get('cpu_temp')) or _num(cpu.get('package_temp_c')),
        'cpu_ghz': _num(t.get('cpu_ghz')) or _num(cpu.get('clock_avg_ghz')),
        'ram_usage': _num(t.get('ram_usage')),
        'gpu_usage': _num(gpu.get('usage_percent')),
        'gpu_temp': _num(gpu.get('temperature_c')),
        'gpu_clock_mhz': _num(gpu.get('core_clock_mhz')),
        'gpu_name': gpu.get('name'),
        'gpus': copy.deepcopy(gpus),
    }


def _stats(values: Iterable[Any]) -> Dict[str, Any]:
    clean = [_num(v) for v in values]
    clean = [v for v in clean if v is not None]
    if not clean:
        return {'samples': 0, 'min': None, 'max': None, 'avg': None}
    return {
        'samples': len(clean),
        'min': round(min(clean), 3),
        'max': round(max(clean), 3),
        'avg': round(sum(clean) / len(clean), 3),
    }


class _StressMonitor:
    """Muestrea telemetría durante carga y aplica sólo límites de seguridad."""

    def __init__(self, sampler: TelemetrySampler):
        self.sampler = sampler
        self.rows: list[Dict[str, Any]] = []
        self.stop_reason: str | None = None
        self._last_sample = 0.0
        self.throttling = ThermalThrottlingDetector(max_samples=120)
        self.peak_throttling: Dict[str, Any] = {}
        self.throttling_state: Dict[str, Any] = {'cpu': {'state': 'N/A'}, 'gpu': {'state': 'N/A'}}

    def sample(self):
        now = time.monotonic()
        if now - self._last_sample < 0.35:
            return
        self._last_sample = now
        if not callable(self.sampler):
            return
        try:
            telemetry = self.sampler() or {}
        except Exception:
            telemetry = {}
        if not isinstance(telemetry, dict):
            return
        row = _telemetry_row(telemetry)
        self.rows.append(row)
        try:
            self.throttling_state = self.throttling.add_sample(telemetry)
            ranks = {'N/A': 0, 'NO_EVIDENCE': 1, 'WATCHING': 2, 'SUSPECTED': 3, 'CONFIRMED': 4}
            for key in ('cpu', 'gpu'):
                current = self.throttling_state.get(key) or {}
                previous = self.peak_throttling.get(key) or {}
                if ranks.get(current.get('state'), 0) >= ranks.get(previous.get('state'), 0):
                    self.peak_throttling[key] = copy.deepcopy(current)
        except Exception:
            pass
        cpu_temp = _num(row.get('cpu_temp'))
        gpu_temps = [_num(g.get('temperature_c')) for g in (row.get('gpus') or []) if isinstance(g, dict)]
        gpu_temp = max((v for v in gpu_temps if v is not None), default=_num(telemetry.get('gpu_temp')))
        if cpu_temp is not None and cpu_temp >= 96.0:
            self.stop_reason = f'Seguridad térmica: CPU alcanzó {cpu_temp:.1f} °C'
        elif gpu_temp is not None and gpu_temp >= 92.0:
            self.stop_reason = f'Seguridad térmica: GPU alcanzó {gpu_temp:.1f} °C'

    @property
    def should_stop(self):
        self.sample()
        return bool(self.stop_reason)

    def summary(self):
        result = {'sample_count': len(self.rows)}
        for key in ('cpu_usage', 'cpu_temp', 'cpu_ghz', 'ram_usage', 'gpu_usage', 'gpu_temp', 'gpu_clock_mhz'):
            result[key] = _stats(row.get(key) for row in self.rows)
        result['throttling'] = copy.deepcopy(self.peak_throttling or self.throttling_state)
        result['gpu_activity_names'] = sorted({row['gpu_name'] for row in self.rows if row.get('gpu_name')})
        result['safety_stop'] = self.stop_reason
        return result


def _cpu_stress(seconds: float, monitor: _StressMonitor, progress_callback: ProgressCallback = None, cancel_check: CancelCheck = None) -> Dict[str, Any]:
    seconds = max(3.0, min(30.0, float(seconds)))
    workers = max(1, min(int(os.cpu_count() or 1), 24))
    block = (b'CorePulse CPU stress\0' * 16384)[:256 * 1024]
    stop = threading.Event()

    def worker():
        digest = b''
        while not stop.is_set():
            digest = hashlib.sha256(block + digest).digest()

    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix='CorePulse-StressCPU') as pool:
        futures = [pool.submit(worker) for _ in range(workers)]
        try:
            deadline = start + seconds
            while time.perf_counter() < deadline and not monitor.should_stop and not (callable(cancel_check) and cancel_check()):
                frac = min(1.0, (time.perf_counter() - start) / seconds)
                _emit(progress_callback, frac, 'CPU · carga multinúcleo', f'{workers} hilos sostenidos')
                time.sleep(0.25)
        finally:
            stop.set()
        for future in futures:
            try:
                future.result(timeout=3)
            except Exception:
                pass
    return {
        'kind': 'CPU_STRESS', 'status': 'CANCELLED' if callable(cancel_check) and cancel_check() else ('SAFETY_STOP' if monitor.stop_reason else 'OK'),
        'duration_s': time.perf_counter() - start, 'provider': 'CorePulse sustained multicore stress',
        'threads': workers, 'reason': 'Cancelado por el usuario' if callable(cancel_check) and cancel_check() else monitor.stop_reason,
    }

def _ram_stress(seconds: float, monitor: _StressMonitor, progress_callback: ProgressCallback = None, cancel_check: CancelCheck = None) -> Dict[str, Any]:
    seconds = max(3.0, min(20.0, float(seconds)))
    size_mb = 192
    try:
        import psutil
        available_mb = int(psutil.virtual_memory().available / (1024 * 1024))
        size_mb = max(64, min(size_mb, max(64, int(available_mb * 0.06))))
    except Exception:
        pass
    size_bytes = int(size_mb * 1024 * 1024)
    try:
        src = bytearray(size_bytes)
        dst = bytearray(size_bytes)
    except MemoryError:
        size_mb = 64
        size_bytes = size_mb * 1024 * 1024
        src = bytearray(size_bytes)
        dst = bytearray(size_bytes)
    seed = b'CorePulse-RAM-Stress' * 4096
    src[:min(len(seed), size_bytes)] = seed[:min(len(seed), size_bytes)]
    start = time.perf_counter()
    view_src = memoryview(src)
    view_dst = memoryview(dst)
    while time.perf_counter() - start < seconds and not monitor.should_stop and not (callable(cancel_check) and cancel_check()):
        view_dst[:] = view_src
        src, dst = dst, src
        view_src = memoryview(src)
        view_dst = memoryview(dst)
        frac = min(1.0, (time.perf_counter() - start) / seconds)
        _emit(progress_callback, frac, 'RAM · presión sostenida', f'{size_mb} MB en copia continua')
    return {
        'kind': 'RAM_STRESS', 'status': 'CANCELLED' if callable(cancel_check) and cancel_check() else ('SAFETY_STOP' if monitor.stop_reason else 'OK'),
        'duration_s': time.perf_counter() - start, 'provider': 'CorePulse sustained memory pressure',
        'working_set_mb': size_mb, 'reason': 'Cancelado por el usuario' if callable(cancel_check) and cancel_check() else monitor.stop_reason,
    }

def _stress_component(result: Dict[str, Any] | None, monitor: _StressMonitor, *, renderer=None) -> Dict[str, Any]:
    result = result if isinstance(result, dict) else {}
    status = str(result.get('status') or 'NO_EVALUABLE').upper()
    output = {
        'status': status,
        'duration_s': _num(result.get('duration_s')),
        'provider': result.get('provider'),
        'telemetry': monitor.summary(),
        'performance_score_used': False,
    }
    for key in ('working_set_mb', 'threads', 'errors_detected'):
        if key in result:
            output[key] = result[key]
    if renderer:
        output['renderer'] = renderer
        matched = [gpu_for_renderer(row.get('gpus') or [], renderer) for row in monitor.rows]
        for metric, source in (('gpu_usage', 'usage_percent'), ('gpu_temp', 'temperature_c'), ('gpu_clock_mhz', 'core_clock_mhz')):
            output['telemetry'][metric] = _stats(g.get(source) for g in matched)
        output['telemetry']['gpu_sensor_match'] = any(bool(g) for g in matched)
    reason = result.get('reason')
    if reason:
        output['reason'] = str(reason)
    return output


def run_stress_suite(*, telemetry_sampler: TelemetrySampler = None, progress_callback: ProgressCallback = None, cancel_check: CancelCheck = None, state_callback=None) -> Dict[str, Any]:
    """Carga sostenida segura. Deliberadamente NO publica throughput/FPS como benchmark."""
    started = time.perf_counter()
    components: Dict[str, Any] = {}
    monitor = _StressMonitor(telemetry_sampler)

    phases = [
        ('cpu', 10.0, 0.00, 0.38),
        ('ram', 7.0, 0.38, 0.66),
        ('gpu', 9.0, 0.66, 1.00),
    ]

    for key, seconds, start, end in phases:
        if callable(cancel_check) and cancel_check():
            components[key] = {
                'status': 'CANCELLED', 'duration_s': 0.0,
                'reason': 'Cancelado por el usuario', 'performance_score_used': False,
                'telemetry': monitor.summary(),
            }
            continue
        if monitor.should_stop:
            components[key] = {
                'status': 'SAFETY_STOP', 'duration_s': 0.0,
                'reason': monitor.stop_reason, 'performance_score_used': False,
                'telemetry': monitor.summary(),
            }
            continue

        if callable(state_callback):
            state_callback(f'RUNNING_STRESS_{key.upper()}')
        local_monitor = _StressMonitor(telemetry_sampler)

        def cb(frac, stage, detail='', _start=start, _end=end, _key=key):
            local_monitor.sample()
            monitor.sample()
            mapped = _start + (_end - _start) * max(0.0, min(1.0, float(frac)))
            _emit(progress_callback, mapped, f'Estrés {_key.upper()}', detail or stage)

        stop_check = lambda: bool(local_monitor.should_stop or monitor.should_stop or (callable(cancel_check) and cancel_check()))
        if key == 'cpu':
            raw = _cpu_stress(seconds, local_monitor, progress_callback=cb, cancel_check=cancel_check)
            components[key] = _stress_component(raw, local_monitor)
        elif key == 'ram':
            raw = _ram_stress(seconds, local_monitor, progress_callback=cb, cancel_check=cancel_check)
            components[key] = _stress_component(raw, local_monitor)
        else:
            # La ruta OpenGL probada se reutiliza únicamente como generador de carga.
            # Mtri/s/FPS no se exponen ni intervienen en la conclusión de estrés.
            raw = benchmark_gpu(timeout=int(seconds + 5), seconds=seconds, progress_callback=cb, stop_check=stop_check)
            components[key] = _stress_component(raw, local_monitor, renderer=raw.get('renderer') if isinstance(raw, dict) else None)

        if local_monitor.stop_reason and not monitor.stop_reason:
            monitor.stop_reason = local_monitor.stop_reason
        # No duplicar muestras globales ni añadir muestras posteriores a la fase.
        if callable(cancel_check) and cancel_check():
            components[key]['status'] = 'CANCELLED'
            components[key]['reason'] = 'Cancelado por el usuario'
        elif local_monitor.stop_reason:
            components[key]['status'] = 'SAFETY_STOP'
            components[key]['reason'] = local_monitor.stop_reason

    statuses = [str((components.get(k) or {}).get('status') or '').upper() for k in ('cpu', 'ram', 'gpu')]
    overall = 'CANCELLED' if 'CANCELLED' in statuses or (callable(cancel_check) and cancel_check()) else ('SAFETY_STOP' if 'SAFETY_STOP' in statuses else 'PARTIAL' if any(s not in {'OK'} for s in statuses) else 'OK')
    _emit(progress_callback, 1.0, 'Estrés cancelado' if overall == 'CANCELLED' else 'Estrés finalizado', 'El benchmark se mide por separado')
    return {
        'status': overall,
        'duration_s': round(time.perf_counter() - started, 3),
        'components': components,
        'telemetry_summary': monitor.summary(),
        'safety_stop': monitor.stop_reason,
        'cancelled': overall == 'CANCELLED',
        'policy': 'STABILITY_UNDER_LOAD_NO_PERFORMANCE_SCORE',
    }


def _finding(component, status, title, explanation, evidence, rule_source):
    return {
        'component': str(component), 'status': str(status).upper(), 'title': str(title),
        'explanation': str(explanation), 'evidence': [str(x) for x in evidence if str(x).strip()],
        'rule_source': str(rule_source),
    }


def _complete_findings(base_result, windows, stress, benchmark, hardware=None):
    findings: list[Dict[str, Any]] = []
    for drive in ((hardware or {}).get('storage') or []):
        if not isinstance(drive, dict):
            continue
        life = physical_health(drive)
        status = str(drive.get('windows_health_status') or '').casefold()
        severity = ('CRITICAL' if life is not None and life < 50 else
                    'WARNING' if life is not None and life < 70 else None)
        if status in {'critical', 'unhealthy', 'failed', 'crítico'}:
            severity = 'CRITICAL'
        elif not severity and status in {'warning', 'advertencia'}:
            severity = 'WARNING'
        if severity:
            evidence = [f"Fuente: {drive.get('health_source') or 'N/A'}"]
            if life is not None:
                evidence.append(f'Vida restante reportada: {life:.0f}%')
            if status:
                evidence.append(f'Estado del sistema: {drive.get("windows_health_status")}')
            findings.append(_finding('STORAGE:' + str(drive.get('name') or drive.get('model') or 'Unidad'),
                severity, 'Almacenamiento requiere revisión',
                'La fuente de salud reporta una condición que requiere revisión; el benchmark no determina salud física.',
                evidence, 'CorePulse health_engine storage policy (<50/<70)' + (' / Windows HealthStatus' if platform.system() == 'Windows' else '')))

    stability = windows.get('stability') if isinstance(windows.get('stability'), dict) else {}
    severity = str(stability.get('severity') or '').upper()
    if severity in {'CRITICAL', 'WARNING'}:
        findings.append(_finding(
            'WINDOWS', severity,
            'Windows registró eventos que requieren revisión',
            str(stability.get('summary') or 'Se detectaron eventos de estabilidad en Windows.'),
            [f"WHEA: {(stability.get('counts') or {}).get('whea', 0)}",
             f"Bugchecks: {(stability.get('counts') or {}).get('bsod_bugcheck', 0)}",
             f"Incidentes de energía: {stability.get('power_event_count', 0)}"],
            'Windows Event Log / analyze_crashes',
        ))

    startup = windows.get('startup') if isinstance(windows.get('startup'), dict) else {}
    degraded = [x for x in (startup.get('items') or []) if isinstance(x, dict) and x.get('degradation_event_seen')]
    if degraded:
        names = [str(x.get('name') or 'Entrada') for x in degraded[:3]]
        findings.append(_finding(
            'WINDOWS_STARTUP', 'WARNING',
            'Windows registró degradación asociada al inicio',
            'Diagnostics-Performance contiene evidencia real de impacto de inicio para una o más entradas.',
            [f'{len(degraded)} entrada(s) con evento 101', 'Ejemplos: ' + ', '.join(names)],
            'Diagnostics-Performance 101',
        ))

    drivers = windows.get('drivers') if isinstance(windows.get('drivers'), dict) else {}
    problems = int(drivers.get('device_problems') or 0)
    if problems > 0:
        findings.append(_finding(
            'DRIVERS', 'WARNING', 'Windows reporta dispositivos con problema',
            'Win32_PnPEntity expone dispositivos con un código de problema actual.',
            [f'{problems} dispositivo(s) con problema'], 'Win32_PnPEntity',
        ))

    for component in ('cpu', 'gpu'):
        item = benchmark.get(component) or {}
        tele = item.get('telemetry') or {}
        throttling = (tele.get('throttling') or {}).get(component) or {}
        state = throttling.get('state')
        if state in {'CONFIRMED', 'SUSPECTED', 'WATCHING'}:
            label = {'CONFIRMED': 'Throttling detectado', 'SUSPECTED': 'Posible limitación',
                     'WATCHING': 'Margen térmico reducido'}[state]
            evidence = list(throttling.get('evidence') or [])
            temp = _num((tele.get(component + '_temp') or {}).get('max'))
            if temp is not None:
                evidence.append(f'Durante benchmark: {temp:.1f} °C máximo')
            if state != 'CONFIRMED':
                evidence.append('No se confirmó throttling mediante sensor explícito')
            findings.append(_finding(component.upper(), 'CRITICAL' if state == 'CONFIRMED' else 'WARNING',
                f'{component.upper()}: {label}', 'Comportamiento observado durante el benchmark.',
                evidence, 'ThermalThrottlingDetector / benchmark'))

    if isinstance(benchmark, dict):
        if benchmark.get('safety_stop'):
            findings.append(_finding(
                ('CPU' if 'CPU' in str(benchmark.get('safety_stop')) else 'GPU' if 'GPU' in str(benchmark.get('safety_stop')) else 'BENCHMARK'), 'CRITICAL', 'Benchmark detenido por seguridad',
                'La suite de rendimiento se detuvo al alcanzar un límite térmico de seguridad.',
                [str(benchmark.get('safety_stop'))], 'Benchmark safety guard',
            ))
        errors = []
        for key in ('cpu', 'ram', 'ssd', 'gpu'):
            item = benchmark.get(key) if isinstance(benchmark.get(key), dict) else {}
            status = str(item.get('status') or '').upper()
            if status in {'ERROR', 'UNAVAILABLE'}:
                errors.append(f"{key.upper()}: {item.get('reason') or status}")
        if errors:
            findings.append(_finding(
                'BENCHMARK', 'NO_EVALUABLE', 'Parte del benchmark no pudo evaluarse',
                'No se convierte un fallo de medición en un fallo de hardware.',
                errors, 'CorePulse benchmark execution status',
            ))

    return findings


def _overall_status(findings, base_status='NO_EVALUABLE', *, force_partial=False):
    statuses = [str((x or {}).get('status') or '').upper() for x in findings if isinstance(x, dict)]
    if 'CRITICAL' in statuses:
        return 'CRITICAL'
    if 'WARNING' in statuses:
        return 'WARNING'
    base = str(base_status or 'NO_EVALUABLE').upper()
    if base in {'CRITICAL', 'WARNING'}:
        return base
    if force_partial:
        return 'NO_EVALUABLE'
    if base == 'NORMAL':
        return 'NORMAL'
    return 'NO_EVALUABLE'


def benchmark_observation(benchmark, components=None, required_components=None):
    """Resume telemetría observada sin penalizar componentes no soportados.

    CPU/RAM/GPU forman la evidencia de carga requerida en Windows y Linux;
    SSD aporta telemetría cuando el sensor existe.
    """
    benchmark = benchmark if isinstance(benchmark, dict) else {}
    if components is None:
        components = tuple(key for key in ('cpu', 'gpu', 'ram', 'ssd') if isinstance(benchmark.get(key), dict))
    components = tuple(components or ())
    required = set(required_components if required_components is not None else components)
    result_components = {}
    metrics_map = {
        'cpu': ('cpu_temp', 'cpu_usage', 'cpu_ghz'),
        'gpu': ('gpu_temp', 'gpu_usage', 'gpu_clock_mhz'),
        'ram': ('ram_usage',),
        'ssd': ('storage_temperature',),
    }
    for key in components:
        item = benchmark.get(key) if isinstance(benchmark.get(key), dict) else {}
        tele = item.get('telemetry') if isinstance(item.get('telemetry'), dict) else {}
        metrics = metrics_map.get(key, ())
        available = bool(tele.get('during_sample_count')) and any((tele.get(m) or {}).get('samples') for m in metrics)
        result_components[key] = {'status': 'MEASURED' if available else 'N/A', 'sample_count': tele.get('during_sample_count', 0)}
    required_ok = all((result_components.get(key) or {}).get('status') == 'MEASURED' for key in required)
    status = 'SAFETY_STOP' if benchmark.get('safety_stop') else ('OK' if required_ok else 'PARTIAL')
    return {'status': status, 'components': result_components, 'source': 'BENCHMARK', 'dedicated_stress_executed': False}


def _cancelled_result(result, hardware, phases, started, *, windows=None, stress=None, benchmark=None):
    """Conserva evidencia parcial sin presentarla como diagnóstico final válido."""
    output = copy.deepcopy(result if isinstance(result, dict) else {})
    output['overall_status'] = 'NO_EVALUABLE'
    output['session_valid'] = False
    output['findings'] = []
    phase_rows = [row for row in phases.values() if isinstance(row, dict)]
    cancelled_payload = {
        'version': '4.1-v162',
        'platform': platform.system(),
        'status': 'CANCELLED',
        'finalized': False,
        'duration_extension_s': round(time.perf_counter() - started, 3),
        'hardware': hardware if isinstance(hardware, dict) else {},
        'load_observation': benchmark_observation(benchmark or {}),
        'benchmark': benchmark if isinstance(benchmark, dict) else {},
        'phases': phases,
        'phase_coverage': {
            'completed': sum(1 for row in phase_rows if str(row.get('status') or '').upper() in {'OK', 'PARTIAL', 'SAFETY_STOP'}),
            'total': max(1, len(phase_rows)),
            'partial': True,
        },
        'repair_actions_executed': False,
        'pdf_optional': False,
        'cancelled_by_user': True,
        'policy': {
            'real_or_na': True,
            'stress_and_benchmark_are_distinct': True,
            'automatic_stress': False,
            'load_source': 'BENCHMARK',
            'automatic_repairs': False,
            'user_cancellable': True,
        },
    }
    if platform.system() == 'Windows' and isinstance(windows, dict):
        cancelled_payload['windows'] = windows
    output['complete_diagnostic'] = cancelled_payload
    output['diagnostic_mode'] = 'COMPLETE_4_0'
    output['complete_duration_seconds'] = round(float(output.get('duration_seconds') or 0.0) + float(output['complete_diagnostic']['duration_extension_s']), 3)
    return output


def run_complete_diagnostic(
    base_result: Dict[str, Any], telemetry_snapshot: Dict[str, Any], disks_snapshot: list[Dict[str, Any]],
    *, telemetry_sampler: TelemetrySampler = None, progress_callback: ProgressCallback = None, cancel_check: CancelCheck = None, state_callback=None,
) -> Dict[str, Any]:
    """Completa la sesión pasiva con diagnóstico específico de la plataforma y benchmark estándar."""
    is_windows = platform.system() == 'Windows'
    started = time.perf_counter()
    result = copy.deepcopy(base_result if isinstance(base_result, dict) else {})
    telemetry_snapshot = copy.deepcopy(telemetry_snapshot if isinstance(telemetry_snapshot, dict) else {})
    disks_snapshot = copy.deepcopy(disks_snapshot if isinstance(disks_snapshot, list) else [])
    phases: Dict[str, Any] = {}

    def is_cancelled():
        try:
            return bool(callable(cancel_check) and cancel_check())
        except Exception:
            return False

    def phase_begin(key, label):
        state = {'hardware': 'RUNNING_HARDWARE', 'windows': 'RUNNING_WINDOWS',
                 'audio': 'RUNNING_AUDIO', 'benchmark': 'RUNNING_BENCHMARK',
                 'load_observation': 'ANALYZING_BENCHMARK',
                 'correlation': 'CORRELATING'}.get(key)
        if state and callable(state_callback):
            state_callback(state)
        phases[key] = {'label': label, 'status': 'RUNNING', 'started_at': time.time(), '_started_perf': time.perf_counter()}

    def phase_end(key, status='OK', detail=''):
        row = phases.setdefault(key, {'label': key})
        begin = row.pop('_started_perf', None)
        row['status'] = str(status).upper()
        row['finished_at'] = time.time()
        row['duration_s'] = round(max(0.0, time.perf_counter() - begin), 3) if isinstance(begin, (int, float)) else None
        if detail:
            row['detail'] = str(detail)

    phases['desktop'] = {
        'label': 'Estado en escritorio',
        'status': 'OK' if bool(result.get('session_valid')) else 'PARTIAL',
        'duration_s': _num(result.get('duration_seconds')),
        'detail': str((result.get('adaptive_diagnostic') or {}).get('finish_reason') or result.get('completion_status') or 'N/A'),
    }

    if is_cancelled():
        return _cancelled_result(result, {}, phases, started)

    phase_begin('hardware', 'Hardware, batería y almacenamiento')
    _emit(progress_callback, 0.02, 'Hardware y batería', 'Consolidando identidad, batería y almacenamiento observados')
    try:
        with cancellation_scope(is_cancelled):
            battery = collect_battery_health(telemetry_snapshot)
    except Exception as exc:
        battery = {'present': None, 'error': f'{type(exc).__name__}: {exc}', 'policy': 'REAL_OR_NA'}
    hardware = {
        'battery': battery,
        'storage': storage_snapshot(telemetry_snapshot, disks_snapshot),
        'volumes': disks_snapshot,
        'telemetry_snapshot': telemetry_snapshot,
        'policy': 'REAL_OR_NA',
    }
    hardware_partial = bool(isinstance(battery, dict) and battery.get('error'))
    phase_end('hardware', 'CANCELLED' if is_cancelled() else ('PARTIAL' if hardware_partial else 'OK'))
    if is_cancelled():
        return _cancelled_result(result, hardware, phases, started)

    windows: Dict[str, Any] = {}
    if is_windows:
        phase_begin('windows', 'Estado de Windows')
        _emit(progress_callback, 0.09, 'Windows', 'Inicio, servicios, estabilidad y controladores en paralelo')
        jobs = {
            'startup': analyze_startup,
            'services': analyze_services,
            'stability': lambda: analyze_crashes(days=7),
            'drivers': lambda: analyze_drivers(limit=400),
        }
        def windows_job(fn):
            with cancellation_scope(is_cancelled):
                return fn()

        windows_results: Dict[str, Any] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix='CorePulse-DiagWindows') as pool:
            future_map = {pool.submit(windows_job, fn): key for key, fn in jobs.items()}
            completed = 0
            for future in concurrent.futures.as_completed(future_map):
                key = future_map[future]
                try:
                    windows_results[key] = future.result()
                except Exception as exc:
                    fallback = {'items': [], 'count': 0, 'error': f'{type(exc).__name__}: {exc}'}
                    if key == 'stability':
                        fallback['severity'] = 'NO_EVALUABLE'
                    windows_results[key] = fallback
                completed += 1
                _emit(progress_callback, 0.09 + 0.15 * (completed / 4.0), 'Windows', f'{completed}/4 análisis completados')
        windows = {
            'startup': windows_results.get('startup', {}),
            'services': windows_results.get('services', {}),
            'stability': windows_results.get('stability', {}),
            'drivers': windows_results.get('drivers', {}),
            'execution': 'PARALLEL_READ_ONLY',
            'policy': 'ANALYZE_ONLY_NO_AUTOMATIC_REPAIR',
        }
        windows_errors_now = any(bool((windows.get(key) or {}).get('error')) for key in ('startup', 'services', 'stability', 'drivers') if isinstance(windows.get(key), dict))
        phase_end('windows', 'PARTIAL' if windows_errors_now else ('CANCELLED' if is_cancelled() else 'OK'))
        if is_cancelled():
            return _cancelled_result(result, hardware, phases, started, windows=windows)

    # V181: el diagnóstico prueba técnicamente audio en ambos sistemas. Se oyen
    # tonos breves izquierda/derecha/ambos; el micrófono se abre ~1 s. Esto
    # verifica la ruta real de E/S sin sustituir la confirmación humana opcional.
    phase_begin('audio', 'Audio automático')
    audio_base = 0.25 if is_windows else 0.09
    _emit(progress_callback, audio_base, 'Audio automático', 'Verificando salida estéreo y acceso al micrófono')
    try:
        audio_probe = automatic_audio_probe(
            progress_callback=lambda frac, stage, detail='': _emit(
                progress_callback, audio_base + (0.06 * float(frac)), stage, detail
            ),
            cancel_check=is_cancelled,
        )
    except Exception as exc:
        audio_probe = {
            'mode': 'AUTOMATIC_TECHNICAL', 'status': 'PROBLEMA REPORTADO',
            'reason': f'{type(exc).__name__}: {exc}', 'devices': {}, 'technical': {},
            'answers': {}, 'errors': [f'{type(exc).__name__}: {exc}'],
        }
    audio_status_now = str(audio_probe.get('status') or '').upper()
    audio_phase_status = ('CANCELLED' if is_cancelled() or audio_status_now == 'CANCELLED' else
                          'OK' if audio_status_now == 'AUDIO TÉCNICO OK' else 'PARTIAL')
    phase_end('audio', audio_phase_status, str(audio_probe.get('reason') or ''))
    if is_cancelled():
        return _cancelled_result(result, hardware, phases, started, windows=windows)

    benchmark_base = 0.32 if is_windows else 0.17
    benchmark_span = 0.62 if is_windows else 0.77
    # GPU ya forma parte de la misma suite en Linux mediante OpenGL/GLX visible.
    benchmark_components = ('cpu', 'ram', 'ssd', 'gpu')
    required_load_components = ('cpu', 'ram', 'gpu')

    def benchmark_progress(frac, stage, detail=''):
        _emit(progress_callback, benchmark_base + benchmark_span * float(frac), f'Benchmark · {stage}', detail)

    phase_begin('benchmark', 'Benchmark estándar')
    _emit(progress_callback, benchmark_base, 'Benchmark estándar', 'Midiendo CPU, RAM, SSD y GPU')
    try:
        benchmark = run_benchmark_suite(
            'standard', benchmark_components,
            progress_callback=benchmark_progress,
            telemetry_sampler=telemetry_sampler,
            cancel_check=is_cancelled,
            storage_inventory=hardware['storage'],
        )
    except Exception as exc:
        benchmark = {'status': 'ERROR', 'error': f'{type(exc).__name__}: {exc}', 'policy': 'LOCAL_CONFIGURABLE_BENCHMARK_NO_REFERENCE_RANKING'}
    benchmark_status_now = str(benchmark.get('status') or ('ERROR' if benchmark.get('error') else 'OK')).upper()
    phase_end('benchmark', benchmark_status_now)
    if is_cancelled() or benchmark_status_now == 'CANCELLED':
        return _cancelled_result(result, hardware, phases, started, windows=windows, benchmark=benchmark)

    phase_begin('load_observation', 'Telemetría durante benchmark')
    _emit(progress_callback, 0.97, 'Analizando telemetría durante benchmark', 'Temperaturas, carga, frecuencias y evidencia de limitación')
    observation = benchmark_observation(benchmark, benchmark_components, required_load_components)
    phase_end('load_observation', observation['status'])
    if is_cancelled():
        return _cancelled_result(result, hardware, phases, started, windows=windows, benchmark=benchmark)

    phase_begin('correlation', 'Correlación final')
    _emit(progress_callback, 0.985, 'Correlacionando evidencia', 'Separando salud, estabilidad y rendimiento medido')
    new_findings = _complete_findings(result, windows, {}, benchmark, hardware)
    existing = [copy.deepcopy(x) for x in (result.get('findings') or []) if isinstance(x, dict)]
    combined = existing + new_findings
    result['findings'] = combined
    windows_partial = is_windows and any(bool((windows.get(key) or {}).get('error')) for key in ('startup', 'services', 'stability', 'drivers') if isinstance(windows.get(key), dict))
    benchmark_partial = bool(benchmark.get('error'))
    if isinstance(benchmark, dict) and not benchmark_partial:
        for key in benchmark_components:
            item = benchmark.get(key) if isinstance(benchmark.get(key), dict) else {}
            if str(item.get('status') or '').upper() not in {'OK'}:
                benchmark_partial = True
                break
    baseline_partial = not bool(result.get('session_valid'))
    audio_partial = str(audio_phase_status).upper() != 'OK'
    phase_partial = bool(baseline_partial or hardware_partial or windows_partial or audio_partial or observation['status'] != 'OK' or benchmark_partial)
    result['overall_status'] = _overall_status(combined, result.get('overall_status'), force_partial=phase_partial)
    if is_cancelled():
        phase_end('correlation', 'CANCELLED')
        return _cancelled_result(result, hardware, phases, started, windows=windows, benchmark=benchmark)
    phase_end('correlation', 'PARTIAL' if phase_partial else 'OK')
    phase_order = ('desktop', 'hardware', 'windows', 'audio', 'benchmark', 'load_observation', 'correlation') if is_windows else ('desktop', 'hardware', 'audio', 'benchmark', 'load_observation', 'correlation')
    phase_rows = [phases.get(k) or {} for k in phase_order]
    completed_phases = sum(1 for row in phase_rows if str(row.get('status') or '').upper() in {'OK', 'PARTIAL', 'SAFETY_STOP'})
    result['corepulse_version'] = VERSION_LABEL
    complete_payload = {
        'version': '4.1-v162',
        'platform': platform.system(),
        'finalized': True,
        'phases': phases,
        'phase_coverage': {'completed': completed_phases, 'total': len(phase_rows), 'partial': phase_partial},
        'status': 'PARTIAL' if phase_partial else 'COMPLETE',
        'started_after_baseline': True,
        'duration_extension_s': round(time.perf_counter() - started, 3),
        'hardware': hardware,
        'audio_test': audio_probe,
        'load_observation': observation,
        'benchmark': benchmark,
        'additional_findings': new_findings,
        'repair_actions_executed': False,
        'pdf_optional': True,
        'policy': {
            'real_or_na': True,
            'stress_and_benchmark_are_distinct': True,
            'automatic_stress': False,
            'load_source': 'BENCHMARK',
            'benchmark_method_versioned': True,
            'stress_publishes_performance_score': False,
            'benchmark_has_external_ranking': False,
            'automatic_repairs': False,
            'user_cancellable': True,
            'history_is_informational_only': True,
        },
    }
    if is_windows:
        complete_payload['windows'] = windows
    result['complete_diagnostic'] = complete_payload
    result['audio_test'] = copy.deepcopy(audio_probe)
    result['diagnostic_mode'] = 'COMPLETE_4_0'
    result['complete_duration_seconds'] = round(float(result.get('duration_seconds') or 0.0) + float(result['complete_diagnostic']['duration_extension_s']), 3)
    _emit(progress_callback, 1.0, 'Diagnóstico completo', 'Resultado consolidado listo; reparaciones y PDF siguen siendo opcionales')
    return result


def save_complete_result(result: Dict[str, Any], output_root: str | os.PathLike | None = None) -> str:
    if not is_finalized_result(result):
        raise ValueError('Sólo se guardan diagnósticos finalizados; cancelaciones y errores no son resultados completos')
    root = Path(output_root) if output_root else Path(diagnostics_dir())
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    path = root / f'diagnostic_complete_{stamp}_{uuid.uuid4().hex[:10]}.json'
    tmp = path.with_suffix(path.suffix + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    os.replace(tmp, path)
    return str(path)
