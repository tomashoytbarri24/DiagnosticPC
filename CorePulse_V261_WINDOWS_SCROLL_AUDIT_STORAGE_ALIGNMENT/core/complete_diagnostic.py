"""Orquestador del Diagnóstico Total 6.0 de CorePulse (V173).

Flujo único: línea base/telemetría → hardware/batería/SSD → Windows e integridad
(read-only) → benchmark → estrés → ventiladores → audio técnico/guiado → limpieza
segura allowlist → correlación → IA/vigencia → PDF opcional.

REAL_OR_NA: no se fabrican sensores, métricas, resultados de benchmark, estado de
parlantes ni clasificaciones cuando falta evidencia. La limpieza automática sólo
borra temporales/cachés recreables previamente revalidados; DISM/SFC/CHKDSK no
reparan Windows dentro del diagnóstico.
"""
from __future__ import annotations

import copy
import concurrent.futures
import hashlib
import json
import math
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from core.battery_health import collect_battery_health
from core.benchmark_engine import benchmark_gpu, run_benchmark_suite
from core.runtime_paths import diagnostics_dir
from core.thermal_throttling import ThermalThrottlingDetector
from core.version import VERSION_LABEL
from core.cancellable_process import cancellation_scope
from core.diagnostic_lifecycle import is_finalized_result
from core.diagnostic_evidence import storage_snapshot, active_gpu, gpu_for_renderer, physical_health
from core.windows_health import analyze_crashes, analyze_drivers, analyze_services, analyze_startup
from core.windows_repair import run_integrity_diagnostic
from core.windows_commands import run_hidden, is_admin
from core.safe_storage_cleanup import scan_safe_storage_cleanup, delete_scanned_candidates
from core.ai_report_engine import analyze_report_with_ai

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
        'cpu_tjmax_distance': _num(cpu.get('distance_to_tjmax_min_c')) or _num(t.get('cpu_tjmax_distance')) or _num(t.get('distance_to_tjmax_min_c')),
        'cpu_ghz': _num(t.get('cpu_ghz')) or _num(cpu.get('clock_avg_ghz')),
        'ram_usage': _num(t.get('ram_usage')),
        'gpu_usage': _num(gpu.get('usage_percent')),
        'gpu_temp': _num(gpu.get('temperature_c')),
        'gpu_clock_mhz': _num(gpu.get('core_clock_mhz')),
        'gpu_fan_rpm': _num(gpu.get('fan_rpm')),
        'gpu_fan_control_percent': _num(gpu.get('fan_control_percent')),
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
        self._cpu_safety_hits = 0
        self._gpu_safety_hits = 0

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
        cpu_distance = _num(row.get('cpu_tjmax_distance'))
        gpu_temps = [_num(g.get('temperature_c')) for g in (row.get('gpus') or []) if isinstance(g, dict)]
        gpu_temp = max((v for v in gpu_temps if v is not None), default=_num(telemetry.get('gpu_temp')))

        # El stress conserva protección, pero deja de usar 96 °C como TjMax universal.
        # Si el sensor expone distancia real a TjMax, esa es la autoridad y exigimos
        # persistencia. Sin ese sensor sólo se usa un fallback extremo.
        if cpu_distance is not None:
            self._cpu_safety_hits = self._cpu_safety_hits + 1 if cpu_distance <= 0.5 else 0
        elif cpu_temp is not None:
            self._cpu_safety_hits = self._cpu_safety_hits + 1 if cpu_temp >= 105.0 else 0
        else:
            self._cpu_safety_hits = 0

        self._gpu_safety_hits = self._gpu_safety_hits + 1 if gpu_temp is not None and gpu_temp >= 95.0 else 0

        if self._cpu_safety_hits >= 3:
            if cpu_distance is not None:
                self.stop_reason = f'Seguridad térmica: CPU permaneció a {cpu_distance:.1f} °C o menos de TjMax'
            else:
                self.stop_reason = f'Seguridad térmica: CPU permaneció en {cpu_temp:.1f} °C sin TjMax disponible'
        elif self._gpu_safety_hits >= 3:
            self.stop_reason = f'Seguridad térmica: GPU permaneció en {gpu_temp:.1f} °C'

    @property
    def should_stop(self):
        self.sample()
        return bool(self.stop_reason)

    def summary(self):
        result = {'sample_count': len(self.rows)}
        for key in ('cpu_usage', 'cpu_temp', 'cpu_tjmax_distance', 'cpu_ghz', 'ram_usage', 'gpu_usage', 'gpu_temp', 'gpu_clock_mhz', 'gpu_fan_rpm', 'gpu_fan_control_percent'):
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
                evidence.append(f'Estado Windows: {drive.get("windows_health_status")}')
            findings.append(_finding('STORAGE:' + str(drive.get('name') or drive.get('model') or 'Unidad'),
                severity, 'Almacenamiento requiere revisión',
                'La fuente de salud reporta una condición que requiere revisión; el benchmark no determina salud física.',
                evidence, 'CorePulse health_engine storage policy (<50/<70) / Windows HealthStatus'))

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


def benchmark_observation(benchmark):
    components = {}
    for key in ('cpu', 'gpu', 'ram', 'ssd'):
        item = benchmark.get(key) or {}
        tele = item.get('telemetry') or {}
        metrics = {'cpu': ('cpu_temp', 'cpu_usage', 'cpu_ghz'),
                   'gpu': ('gpu_temp', 'gpu_usage', 'gpu_clock_mhz'),
                   'ram': ('ram_usage',), 'ssd': ('storage_temperature',)}[key]
        available = bool(tele.get('during_sample_count')) and any((tele.get(m) or {}).get('samples') for m in metrics)
        components[key] = {'status': 'MEASURED' if available else 'N/A',
                           'sample_count': tele.get('during_sample_count', 0)}
    status = 'SAFETY_STOP' if benchmark.get('safety_stop') else ('OK' if all(c['status'] == 'MEASURED' for c in components.values()) else 'PARTIAL')
    return {'status': status, 'components': components, 'source': 'BENCHMARK',
            'dedicated_stress_executed': False}


def _cancelled_result(result, hardware, phases, started, *, windows=None, stress=None, benchmark=None, cleanup=None, ai_analysis=None):
    """Conserva evidencia parcial sin presentarla como diagnóstico final válido."""
    output = copy.deepcopy(result if isinstance(result, dict) else {})
    output['overall_status'] = 'NO_EVALUABLE'
    output['session_valid'] = False
    output['findings'] = []
    phase_rows = [row for row in phases.values() if isinstance(row, dict)]
    output['complete_diagnostic'] = {
        'version': '6.0-v169',
        'status': 'CANCELLED',
        'finalized': False,
        'duration_extension_s': round(time.perf_counter() - started, 3),
        'hardware': hardware if isinstance(hardware, dict) else {},
        'windows': windows if isinstance(windows, dict) else {},
        'load_observation': benchmark_observation(benchmark or {}),
        'benchmark': benchmark if isinstance(benchmark, dict) else {},
        'stress': stress if isinstance(stress, dict) else {},
        'cleanup': cleanup if isinstance(cleanup, dict) else {},
        'ai_analysis': ai_analysis if isinstance(ai_analysis, dict) else {},
        'phases': phases,
        'phase_coverage': {
            'completed': sum(1 for row in phase_rows if str(row.get('status') or '').upper() in {'OK', 'PARTIAL', 'SAFETY_STOP'}),
            'total': 11,
            'partial': True,
        },
        'repair_actions_executed': False,
        'pdf_optional': False,
        'cancelled_by_user': True,
        'policy': {
            'real_or_na': True,
            'stress_and_benchmark_are_distinct': True,
            'automatic_stress': True,
            'load_source': 'BENCHMARK',
            'automatic_repairs': False,
            'automatic_safe_cleanup': True,
            'user_cancellable': True,
        },
    }
    output['diagnostic_mode'] = 'COMPLETE_6_0'
    output['complete_duration_seconds'] = round(float(output.get('duration_seconds') or 0.0) + float(output['complete_diagnostic']['duration_extension_s']), 3)
    return output


def _filesystem_integrity_scan() -> Dict[str, Any]:
    """CHKDSK /scan del volumen de Windows. Sólo diagnóstico; no repara nada."""
    if os.name != 'nt':
        return {'status': 'UNAVAILABLE', 'reason': 'Windows requerido', 'policy': 'READ_ONLY_REAL_OR_NA'}
    if not is_admin():
        return {'status': 'ADMIN_REQUIRED', 'reason': 'CHKDSK /scan requiere privilegios de administrador', 'policy': 'READ_ONLY_REAL_OR_NA'}
    drive = str(os.environ.get('SystemDrive') or 'C:').strip() or 'C:'
    args = ('chkdsk.exe', drive, '/scan')
    started = time.perf_counter()
    result = run_hidden(args, timeout=1800.0, category='WINDOWS_DIAGNOSTIC')
    raw = '\n'.join(x for x in (result.stdout, result.stderr, result.error or '') if x).strip()
    status = 'OK' if result.ok else ('TIMEOUT' if result.timed_out else 'ATTENTION_REQUIRED')
    return {
        'status': status,
        'drive': drive,
        'command': list(args),
        'returncode': result.returncode,
        'duration_s': round(time.perf_counter() - started, 3),
        'stdout': result.stdout,
        'stderr': result.stderr,
        'error': result.error,
        'raw_available': bool(raw),
        'mutating': False,
        'policy': 'READ_ONLY_REAL_OR_NA',
    }


def _fan_observation(stress: Dict[str, Any] | None) -> Dict[str, Any]:
    """Resume únicamente RPM/control realmente observados durante estrés."""
    stress = stress if isinstance(stress, dict) else {}
    components = stress.get('components') if isinstance(stress.get('components'), dict) else {}
    rpm_values = []
    control_values = []
    evidence = []
    for key in ('cpu', 'ram', 'gpu'):
        block = components.get(key) if isinstance(components.get(key), dict) else {}
        telemetry = block.get('telemetry') if isinstance(block.get('telemetry'), dict) else {}
        rpm = telemetry.get('gpu_fan_rpm') if isinstance(telemetry.get('gpu_fan_rpm'), dict) else {}
        ctl = telemetry.get('gpu_fan_control_percent') if isinstance(telemetry.get('gpu_fan_control_percent'), dict) else {}
        for field in ('min', 'max', 'avg'):
            value = _num(rpm.get(field))
            if value is not None:
                rpm_values.append(value)
            value = _num(ctl.get(field))
            if value is not None:
                control_values.append(value)
        if int(rpm.get('samples') or 0) > 0:
            evidence.append(f"{key.upper()}: ventilador GPU {rpm.get('min')}–{rpm.get('max')} RPM ({rpm.get('samples')} muestras)")
    if not rpm_values and not control_values:
        return {
            'status': 'N/A',
            'reason': 'El hardware/driver no expuso RPM ni control de ventilador durante la prueba.',
            'response_observed': None,
            'policy': 'REAL_OR_NA',
            'evidence': [],
        }
    rpm_min = min(rpm_values) if rpm_values else None
    rpm_max = max(rpm_values) if rpm_values else None
    ctl_min = min(control_values) if control_values else None
    ctl_max = max(control_values) if control_values else None
    rpm_delta = (rpm_max - rpm_min) if rpm_min is not None and rpm_max is not None else None
    ctl_delta = (ctl_max - ctl_min) if ctl_min is not None and ctl_max is not None else None
    response = bool((rpm_delta is not None and rpm_delta >= 100.0) or (ctl_delta is not None and ctl_delta >= 5.0))
    return {
        'status': 'MEASURED',
        'fan_rpm_min': rpm_min,
        'fan_rpm_max': rpm_max,
        'fan_rpm_delta': rpm_delta,
        'fan_control_min_percent': ctl_min,
        'fan_control_max_percent': ctl_max,
        'fan_control_delta_percent': ctl_delta,
        'response_observed': response,
        'interpretation': ('Se observó una respuesta del ventilador durante la carga.' if response else
                           'Se midió el ventilador, pero esta sesión no demuestra por sí sola un cambio de velocidad.'),
        'evidence': evidence,
        'policy': 'REAL_OR_NA_NO_FAILURE_INFERENCE_WITHOUT_SENSOR_EVIDENCE',
    }


def _audio_observation(cancel_check: CancelCheck = None) -> Dict[str, Any]:
    """Prueba de audio del diagnóstico.

    Si existe confirmación humana reciente, la reutiliza. Si no existe, ejecuta
    tonos reales WASAPI en el endpoint predeterminado para comprobar la ruta
    técnica de salida. Esa reproducción NO permite afirmar que el parlante físico
    se oyó: la verificación acústica permanece N/A hasta confirmación humana.
    """
    try:
        from core.audio_test import recent_audio_result, summary
        result = recent_audio_result()
        status = summary(result)
        if status in {'AUDIO VERIFICADO', 'PROBLEMA REPORTADO', 'VERIFICACIÓN PARCIAL'}:
            return {
                'status': status, 'result': result,
                'user_action_required': status not in {'AUDIO VERIFICADO', 'PROBLEMA REPORTADO'},
                'technical_playback_executed': False,
                'acoustic_confirmation': status == 'AUDIO VERIFICADO',
                'policy': 'GUIDED_HUMAN_CONFIRMATION_REAL_OR_NA',
            }
    except Exception:
        result = {}

    try:
        from core.windows_audio import WindowsAudio
        provider = WindowsAudio()
        devices = provider.devices()
        output = devices.get('output') if isinstance(devices.get('output'), dict) else {}
        if not output.get('available') or not output.get('id'):
            return {
                'status': 'NO EVALUADO', 'result': {'devices': devices},
                'reason': output.get('error') or 'No hay salida de audio evaluable.',
                'user_action_required': True, 'technical_playback_executed': False,
                'acoustic_confirmation': None, 'policy': 'REAL_OR_NA',
            }
        cancel_event = threading.Event()
        tested = []
        channels = ('left', 'right', 'both') if output.get('stereo') is not False else ('both',)
        for channel in channels:
            if callable(cancel_check) and cancel_check():
                cancel_event.set()
                return {
                    'status': 'CANCELLED', 'result': {'devices': devices, 'technical_channels': tested},
                    'user_action_required': True, 'technical_playback_executed': bool(tested),
                    'acoustic_confirmation': None, 'policy': 'REAL_OR_NA',
                }
            provider.play(channel, output['id'], cancel_event)
            tested.append({'channel': channel, 'api_completed': True})
        technical_result = {
            'schema': 2, 'timestamp': time.time(), 'devices': devices,
            'technical_channels': tested, 'status': 'PRUEBA TÉCNICA COMPLETADA',
            'reason': 'WASAPI completó la reproducción de tonos. La audición física requiere confirmación humana.',
        }
        return {
            'status': 'PRUEBA TÉCNICA COMPLETADA', 'result': technical_result,
            'user_action_required': True, 'technical_playback_executed': True,
            'acoustic_confirmation': None,
            'policy': 'TECHNICAL_PLAYBACK_REAL_ACOUSTIC_CONFIRMATION_NA',
        }
    except Exception as exc:
        return {
            'status': 'NO EVALUADO', 'result': result if isinstance(result, dict) else {},
            'error': f'{type(exc).__name__}: {exc}', 'user_action_required': True,
            'technical_playback_executed': False, 'acoustic_confirmation': None,
            'policy': 'REAL_OR_NA',
        }


def _safe_cleanup_phase(cancel_check: CancelCheck = None) -> Dict[str, Any]:
    """Limpieza segura explícitamente autorizada por Iniciar diagnóstico.

    Sólo borra candidatos recreables de la allowlist de safe_storage_cleanup.
    No toca documentos, descargas, juegos, registro ni archivos desconocidos.
    """
    started = time.perf_counter()
    try:
        scan = scan_safe_storage_cleanup()
    except Exception as exc:
        return {
            'status': 'UNAVAILABLE', 'error': f'{type(exc).__name__}: {exc}',
            'duration_s': round(time.perf_counter() - started, 3),
            'policy': 'ALLOWLIST_RECREATABLE_ONLY_REAL_OR_NA',
            'mutating': False,
        }
    if callable(cancel_check) and cancel_check():
        return {
            'status': 'CANCELLED', 'scan': scan, 'duration_s': round(time.perf_counter() - started, 3),
            'policy': 'ALLOWLIST_RECREATABLE_ONLY_REAL_OR_NA', 'mutating': False,
        }
    candidates = list(scan.get('candidates') or [])
    if not candidates:
        return {
            'status': 'OK', 'scan': scan, 'deleted_files': 0, 'deleted_bytes': 0,
            'free_space_delta_bytes': 0, 'duration_s': round(time.perf_counter() - started, 3),
            'policy': 'ALLOWLIST_RECREATABLE_ONLY_REAL_OR_NA', 'mutating': False,
            'summary': 'No había archivos seguros elegibles para limpiar.',
        }
    try:
        cleaned = delete_scanned_candidates(scan)
        deleted_files = int(cleaned.get('deleted_files') or 0)
        deleted_bytes = int(cleaned.get('deleted_bytes') or 0)
        return {
            'status': 'OK', 'scan': {k: v for k, v in scan.items() if k != 'candidates'},
            'deleted_files': deleted_files, 'deleted_bytes': deleted_bytes,
            'skipped': int(cleaned.get('skipped') or 0),
            'free_space_delta_bytes': cleaned.get('free_space_delta_bytes'),
            'measured_units': cleaned.get('measured_units'),
            'by_category': cleaned.get('by_category') or {},
            'duration_s': round(time.perf_counter() - started, 3),
            'policy': 'ALLOWLIST_RECREATABLE_ONLY_REAL_OR_NA',
            'mutating': bool(deleted_files),
            'summary': f'Se eliminaron {deleted_files} archivo(s) seguros de caché/temporales ({deleted_bytes} bytes medidos).',
        }
    except Exception as exc:
        return {
            'status': 'PARTIAL', 'scan': {k: v for k, v in scan.items() if k != 'candidates'},
            'error': f'{type(exc).__name__}: {exc}',
            'duration_s': round(time.perf_counter() - started, 3),
            'policy': 'ALLOWLIST_RECREATABLE_ONLY_REAL_OR_NA', 'mutating': False,
        }


def _integrity_findings(integrity: Dict[str, Any] | None) -> list[Dict[str, Any]]:
    findings = []
    integrity = integrity if isinstance(integrity, dict) else {}
    dism_sfc = integrity.get('dism_sfc') if isinstance(integrity.get('dism_sfc'), dict) else {}
    state = str(dism_sfc.get('overall_state') or '').upper()
    if state in {'REPAIR_RECOMMENDED', 'ATTENTION_REQUIRED'}:
        findings.append(_finding(
            'WINDOWS_INTEGRITY', 'WARNING' if state == 'REPAIR_RECOMMENDED' else 'CRITICAL',
            'Windows requiere revisión de integridad',
            str(dism_sfc.get('summary') or 'DISM/SFC detectó una condición que requiere revisión.'),
            [f"{row.get('label')}: {row.get('state')}" for row in (dism_sfc.get('steps') or []) if isinstance(row, dict)],
            'DISM CheckHealth/ScanHealth + SFC VerifyOnly',
        ))
    fs = integrity.get('filesystem') if isinstance(integrity.get('filesystem'), dict) else {}
    if str(fs.get('status') or '').upper() in {'ATTENTION_REQUIRED', 'TIMEOUT'}:
        findings.append(_finding(
            'FILESYSTEM', 'WARNING', 'El escaneo del sistema de archivos requiere revisión',
            'CHKDSK /scan no terminó en estado limpio/evaluable.',
            [f"Unidad: {fs.get('drive') or 'N/A'}", f"Código: {fs.get('returncode')}", str(fs.get('error') or '')],
            'CHKDSK /scan',
        ))
    return findings


def _stress_findings(stress: Dict[str, Any] | None) -> list[Dict[str, Any]]:
    findings = []
    stress = stress if isinstance(stress, dict) else {}
    if stress.get('safety_stop'):
        findings.append(_finding(
            'STRESS', 'CRITICAL', 'Prueba de estrés detenida por seguridad',
            'CorePulse detuvo la carga sostenida al alcanzar un límite de seguridad.',
            [str(stress.get('safety_stop'))], 'CorePulse stress safety guard',
        ))
    for key, block in ((stress.get('components') or {}).items() if isinstance(stress.get('components'), dict) else []):
        if not isinstance(block, dict):
            continue
        status = str(block.get('status') or '').upper()
        if status in {'ERROR', 'SAFETY_STOP'}:
            findings.append(_finding(
                str(key).upper(), 'CRITICAL' if status == 'SAFETY_STOP' else 'WARNING',
                f'{str(key).upper()}: estabilidad bajo carga requiere revisión',
                str(block.get('reason') or status),
                [f"Estado: {status}", f"Duración: {block.get('duration_s')} s"],
                'CorePulse dedicated stress suite',
            ))
    return findings


def run_complete_diagnostic(
    base_result: Dict[str, Any], telemetry_snapshot: Dict[str, Any], disks_snapshot: list[Dict[str, Any]],
    *, telemetry_sampler: TelemetrySampler = None, progress_callback: ProgressCallback = None, cancel_check: CancelCheck = None, state_callback=None,
) -> Dict[str, Any]:
    """Diagnóstico Total V173: telemetría → hardware → Windows/integridad → benchmark → estrés → ventiladores → audio → limpieza segura → correlación → IA → PDF opcional."""
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

    state_map = {
        'hardware': 'RUNNING_HARDWARE',
        'windows': 'RUNNING_WINDOWS',
        'integrity': 'RUNNING_INTEGRITY',
        'benchmark': 'RUNNING_BENCHMARK',
        'stress': 'RUNNING_STRESS_CPU',
        'fans': 'RUNNING_FANS',
        'audio': 'RUNNING_AUDIO',
        'cleanup': 'RUNNING_CLEANUP',
        'correlation': 'CORRELATING',
        'ai': 'RUNNING_AI',
    }

    def phase_begin(key, label):
        state = state_map.get(key)
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
        'label': 'Telemetría inicial',
        'status': 'OK' if bool(result.get('session_valid')) else 'PARTIAL',
        'duration_s': _num(result.get('duration_seconds')),
        'detail': str((result.get('adaptive_diagnostic') or {}).get('finish_reason') or result.get('completion_status') or 'N/A'),
    }
    if is_cancelled():
        return _cancelled_result(result, {}, phases, started)

    # 1) Componentes, sensores, batería y almacenamiento
    phase_begin('hardware', 'Componentes, sensores y batería')
    _emit(progress_callback, 0.02, 'Componentes y sensores', 'Identidad, temperaturas, uso, batería y almacenamiento con datos reales o N/A')
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
    phase_end('hardware', 'PARTIAL' if hardware_partial else 'OK')
    if is_cancelled():
        return _cancelled_result(result, hardware, phases, started)

    # 2) Estado Windows
    phase_begin('windows', 'Estado de Windows')
    _emit(progress_callback, 0.08, 'Windows', 'Inicio, servicios, estabilidad y controladores')
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
            _emit(progress_callback, 0.08 + 0.08 * (completed / 4.0), 'Windows', f'{completed}/4 análisis completados')
    windows = {
        'startup': windows_results.get('startup', {}),
        'services': windows_results.get('services', {}),
        'stability': windows_results.get('stability', {}),
        'drivers': windows_results.get('drivers', {}),
        'execution': 'PARALLEL_READ_ONLY',
        'policy': 'ANALYZE_ONLY_NO_AUTOMATIC_REPAIR',
    }
    windows_errors_now = any(bool((windows.get(key) or {}).get('error')) for key in ('startup', 'services', 'stability', 'drivers') if isinstance(windows.get(key), dict))
    phase_end('windows', 'PARTIAL' if windows_errors_now else 'OK')
    if is_cancelled():
        return _cancelled_result(result, hardware, phases, started, windows=windows)

    # 3) Integridad de Windows y sistema de archivos (solo diagnóstico)
    phase_begin('integrity', 'Integridad de Windows y disco')
    _emit(progress_callback, 0.17, 'Integridad de Windows', 'DISM CheckHealth/ScanHealth + SFC VerifyOnly + CHKDSK /scan; no repara automáticamente')
    try:
        dism_sfc = run_integrity_diagnostic()
    except Exception as exc:
        dism_sfc = {'overall_state': 'UNAVAILABLE', 'error': f'{type(exc).__name__}: {exc}', 'steps': []}
    if is_cancelled():
        return _cancelled_result(result, hardware, phases, started, windows=windows)
    _emit(progress_callback, 0.28, 'Sistema de archivos', 'Ejecutando CHKDSK /scan sobre la unidad de Windows')
    try:
        filesystem = _filesystem_integrity_scan()
    except Exception as exc:
        filesystem = {'status': 'UNAVAILABLE', 'error': f'{type(exc).__name__}: {exc}', 'policy': 'READ_ONLY_REAL_OR_NA'}
    integrity = {'dism_sfc': dism_sfc, 'filesystem': filesystem, 'repair_actions_executed': False, 'policy': 'DIAGNOSTIC_ONLY'}
    windows['integrity'] = integrity
    integ_state = str(dism_sfc.get('overall_state') or '').upper()
    fs_state = str(filesystem.get('status') or '').upper()
    integ_partial = integ_state in {'UNAVAILABLE', 'ADMIN_REQUIRED', 'ATTENTION_REQUIRED', 'REPAIR_RECOMMENDED', 'UNKNOWN'} or fs_state not in {'OK'}
    phase_end('integrity', 'PARTIAL' if integ_partial else 'OK')
    if is_cancelled():
        return _cancelled_result(result, hardware, phases, started, windows=windows)

    # 4) Benchmark: rendimiento, NO estabilidad
    def benchmark_progress(frac, stage, detail=''):
        _emit(progress_callback, 0.36 + 0.32 * max(0.0, min(1.0, float(frac))), f'Benchmark · {stage}', detail)
    phase_begin('benchmark', 'Benchmark de componentes')
    _emit(progress_callback, 0.36, 'Benchmark', 'Midiendo CPU, RAM, SSD y GPU con workloads separados')
    try:
        benchmark = run_benchmark_suite(
            'standard', ('cpu', 'ram', 'ssd', 'gpu'),
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

    # 5) Estrés: estabilidad bajo carga, NO score de rendimiento
    def stress_progress(frac, stage, detail=''):
        _emit(progress_callback, 0.69 + 0.20 * max(0.0, min(1.0, float(frac))), stage, detail)
    phase_begin('stress', 'Prueba de estrés')
    _emit(progress_callback, 0.69, 'Prueba de estrés', 'CPU → RAM → GPU; seguridad térmica activa; no genera score')
    try:
        stress = run_stress_suite(
            telemetry_sampler=telemetry_sampler,
            progress_callback=stress_progress,
            cancel_check=is_cancelled,
            state_callback=state_callback,
        )
    except Exception as exc:
        stress = {'status': 'ERROR', 'error': f'{type(exc).__name__}: {exc}', 'components': {}, 'policy': 'STABILITY_UNDER_LOAD_NO_PERFORMANCE_SCORE'}
    stress_status = str(stress.get('status') or 'ERROR').upper()
    phase_end('stress', stress_status)
    if is_cancelled() or stress_status == 'CANCELLED':
        return _cancelled_result(result, hardware, phases, started, windows=windows, stress=stress, benchmark=benchmark)

    # 6) Ventiladores: sólo lo que sensores reales permiten observar
    phase_begin('fans', 'Respuesta de ventiladores')
    _emit(progress_callback, 0.90, 'Ventiladores', 'Analizando RPM/control observados durante las cargas; si no hay sensor, queda N/A')
    fans = _fan_observation(stress)
    phase_end('fans', 'OK' if fans.get('status') == 'MEASURED' else 'PARTIAL', str(fans.get('interpretation') or fans.get('reason') or ''))

    # 7) Audio: evidencia guiada reciente; la audición humana no se inventa
    phase_begin('audio', 'Audio y micrófono')
    _emit(progress_callback, 0.92, 'Audio', 'Comprobando salida de parlantes/canales y evidencia guiada disponible')
    audio = _audio_observation(is_cancelled)
    audio_status = str(audio.get('status') or 'NO EVALUADO').upper()
    audio_ok = audio_status in {'AUDIO VERIFICADO', 'PRUEBA TÉCNICA COMPLETADA'}
    phase_end('audio', 'OK' if audio_ok else ('WARNING' if audio_status == 'PROBLEMA REPORTADO' else 'PARTIAL'))

    # 8) Limpieza segura. Al iniciar el diagnóstico el usuario autorizó esta fase.
    # Sólo actúa sobre la allowlist recreable de CorePulse; Windows/registro/documentos no se reparan ni borran.
    phase_begin('cleanup', 'Limpieza segura del sistema')
    _emit(progress_callback, 0.94, 'Limpieza segura', 'Analizando temporales/cachés recreables y eliminando únicamente candidatos verificados por allowlist')
    cleanup = _safe_cleanup_phase(is_cancelled)
    cleanup_status = str(cleanup.get('status') or 'UNAVAILABLE').upper()
    phase_end('cleanup', 'OK' if cleanup_status == 'OK' else ('PARTIAL' if cleanup_status in {'PARTIAL', 'UNAVAILABLE'} else cleanup_status), str(cleanup.get('summary') or cleanup.get('error') or ''))
    if is_cancelled():
        return _cancelled_result(result, hardware, phases, started, windows=windows, stress=stress, benchmark=benchmark, cleanup=cleanup)

    # 9) Correlación determinística: un diagnóstico, no un promedio ni ranking externo.
    phase_begin('correlation', 'Correlación final')
    _emit(progress_callback, 0.96, 'Correlacionando diagnóstico', 'Salud + Windows + benchmark + estrés + ventiladores + audio + limpieza; sólo evidencia de esta máquina')
    observation = benchmark_observation(benchmark)
    observation['dedicated_stress_executed'] = True
    observation['stress_status'] = stress_status
    new_findings = _complete_findings(result, windows, stress, benchmark, hardware)
    new_findings.extend(_integrity_findings(integrity))
    new_findings.extend(_stress_findings(stress))
    if audio_status == 'PROBLEMA REPORTADO':
        new_findings.append(_finding('AUDIO', 'WARNING', 'Prueba de audio reportó un problema',
            'La prueba guiada fue completada y el usuario reportó que al menos una reproducción no se oyó correctamente.',
            ['Resultado guiado: PROBLEMA REPORTADO'], 'CorePulse guided audio test'))
    existing = [copy.deepcopy(x) for x in (result.get('findings') or []) if isinstance(x, dict)]
    combined = existing + new_findings
    result['findings'] = combined

    benchmark_partial = bool(benchmark.get('error')) or any(
        str((benchmark.get(k) or {}).get('status') or '').upper() != 'OK' for k in ('cpu', 'ram', 'ssd', 'gpu')
    )
    stress_partial = stress_status not in {'OK'}
    baseline_partial = not bool(result.get('session_valid'))
    phase_partial = bool(baseline_partial or hardware_partial or windows_errors_now or integ_partial or benchmark_partial or stress_partial)
    result['overall_status'] = _overall_status(combined, result.get('overall_status'), force_partial=phase_partial)
    phase_end('correlation', 'PARTIAL' if phase_partial else 'OK')

    # Se congela una vista provisional completa para que la IA analice exactamente
    # la misma evidencia que verá el usuario/PDF. No puede inventar métricas faltantes.
    provisional_complete = {
        'version': '6.0-v169', 'finalized': False, 'status': 'BUILDING_AI',
        'hardware': hardware, 'windows': windows, 'integrity': integrity,
        'load_observation': observation, 'benchmark': benchmark, 'stress': stress,
        'fan_test': fans, 'audio_test': audio, 'cleanup': cleanup,
        'additional_findings': new_findings, 'repair_actions_executed': False,
        'cleanup_actions_executed': bool(cleanup.get('mutating')),
    }
    result['complete_diagnostic'] = provisional_complete

    # 10) IA: vigencia anual + explicación del diagnóstico.
    phase_begin('ai', 'Análisis IA y vigencia del hardware')
    _emit(progress_callback, 0.98, 'IA · análisis final', f'Interpretando sólo evidencia real y evaluando vigencia para {datetime.now().year}')
    try:
        ai_analysis = analyze_report_with_ai(result, telemetry_snapshot, disks_snapshot)
    except Exception as exc:
        ai_analysis = {
            'status': 'UNAVAILABLE', 'year': datetime.now().year,
            'executive_summary': 'La capa IA no estuvo disponible; el diagnóstico técnico sigue siendo válido.',
            'hardware_relevance': [], 'limitations': [f'{type(exc).__name__}: {exc}'],
            'policy': 'REAL_EVIDENCE_ONLY_NO_SYNTHETIC_FALLBACK',
        }
    ai_status = str(ai_analysis.get('status') or 'UNAVAILABLE').upper()
    phase_end('ai', 'OK' if ai_status == 'OK' else 'PARTIAL', str(ai_analysis.get('executive_summary') or ai_analysis.get('reason') or ''))
    cleanup_partial = cleanup_status not in {'OK'}
    ai_partial = ai_status not in {'OK'}
    final_partial = bool(phase_partial or cleanup_partial or ai_partial)

    phase_order = ('desktop', 'hardware', 'windows', 'integrity', 'benchmark', 'stress', 'fans', 'audio', 'cleanup', 'correlation', 'ai')
    phase_rows = [phases.get(k) or {} for k in phase_order]
    completed_phases = sum(1 for row in phase_rows if str(row.get('status') or '').upper() in {'OK', 'PARTIAL', 'WARNING', 'SAFETY_STOP'})
    result['corepulse_version'] = VERSION_LABEL
    result['complete_diagnostic'] = {
        'version': '6.0-v169',
        'finalized': True,
        'phases': phases,
        'phase_order': list(phase_order),
        'phase_coverage': {'completed': completed_phases, 'total': len(phase_rows), 'partial': final_partial},
        'status': 'PARTIAL' if final_partial else 'COMPLETE',
        'started_after_baseline': True,
        'duration_extension_s': round(time.perf_counter() - started, 3),
        'hardware': hardware,
        'windows': windows,
        'integrity': integrity,
        'load_observation': observation,
        'benchmark': benchmark,
        'stress': stress,
        'fan_test': fans,
        'audio_test': audio,
        'cleanup': cleanup,
        'ai_analysis': ai_analysis,
        'additional_findings': new_findings,
        'repair_actions_executed': False,
        'cleanup_actions_executed': bool(cleanup.get('mutating')),
        'pdf_optional': True,
        'policy': {
            'real_or_na': True,
            'single_complete_diagnostic_flow': True,
            'benchmark_and_stress_are_distinct': True,
            'automatic_stress': True,
            'stress_publishes_performance_score': False,
            'benchmark_has_external_ranking': False,
            'automatic_windows_repairs': False,
            'automatic_safe_cleanup': True,
            'cleanup_allowlist_recreatable_only': True,
            'windows_integrity_is_diagnostic_only': True,
            'audio_requires_human_confirmation': True,
            'fan_failure_not_inferred_without_sensor_evidence': True,
            'ai_interprets_real_evidence_only': True,
            'hardware_relevance_uses_runtime_year': True,
            'history_is_informational_only': True,
        },
    }
    result['_ai_analysis'] = ai_analysis
    result['audio_test'] = audio.get('result') if isinstance(audio.get('result'), dict) else {}
    result['diagnostic_mode'] = 'COMPLETE_6_0'
    result['complete_duration_seconds'] = round(float(result.get('duration_seconds') or 0.0) + float(result['complete_diagnostic']['duration_extension_s']), 3)
    _emit(progress_callback, 1.0, 'Diagnóstico Total 6.0 completo', 'Resultados, IA y vigencia disponibles en la pestaña. PDF opcional habilitado.')
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
