"""Interpretación estructurada del Diagnóstico Completo.

V146 centraliza el resumen por componente para que la interfaz y el PDF
compartan exactamente la misma lectura. No genera puntuaciones, rankings ni
valores sintéticos: reorganiza evidencia ya presente en el resultado.
"""
from __future__ import annotations

import math
import platform
from core.diagnostic_evidence import physical_health
from typing import Any, Dict, Iterable, List, Optional

STATUS_PRIORITY = {'CRITICAL': 0, 'WARNING': 1, 'NO_EVALUABLE': 2, 'NORMAL': 3, 'INFO': 4}


_EMPTY_DISPLAY_VALUES = {
    '', 'N/A', 'NA', 'NONE', 'NULL', 'UNKNOWN', 'DESCONOCIDO', 'NO EVALUADO',
    'NO EVALUADA', 'NO DISPONIBLE', 'SIN SENSOR', '—', '-',
}


def has_meaningful_value(value: Any) -> bool:
    """Indica si un valor aporta información real para la presentación.

    El motor conserva REAL_OR_NA internamente, pero la interfaz no necesita
    llenar tarjetas con N/A cuando ya existe otra evidencia útil del mismo
    componente.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    text = str(value).strip()
    return text.upper() not in _EMPTY_DISPLAY_VALUES


def filter_meaningful_facets(facets: Iterable[Any]) -> List[Any]:
    rows = []
    for facet in facets or ():
        if not isinstance(facet, (list, tuple)) or len(facet) < 2:
            continue
        if has_meaningful_value(facet[1]):
            rows.append(facet)
    return rows


def _num(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def _status(value, fallback='NO_EVALUABLE'):
    text = str(value or fallback).upper()
    return text if text in {'CRITICAL', 'WARNING', 'NORMAL', 'NO_EVALUABLE', 'INFO'} else fallback


def _findings(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = [x for x in (result.get('findings') or []) if isinstance(x, dict)]
    rows.sort(key=lambda f: (STATUS_PRIORITY.get(_status(f.get('status')), 9), str(f.get('component') or '')))
    return rows


def _matching_findings(result: Dict[str, Any], components: Iterable[str]) -> List[Dict[str, Any]]:
    wanted = {str(x).upper() for x in components}
    matches = []
    for finding in _findings(result):
        component = str(finding.get('component') or '').upper()
        if component in wanted or any(component.startswith(prefix + ':') for prefix in wanted):
            matches.append(finding)
    return matches


def _finding_for(result: Dict[str, Any], components: Iterable[str]) -> Optional[Dict[str, Any]]:
    matches = _matching_findings(result, components)
    return matches[0] if matches else None


def _actionable_finding_for(result: Dict[str, Any], components: Iterable[str]) -> Optional[Dict[str, Any]]:
    for finding in _matching_findings(result, components):
        if _status(finding.get('status')) in {'CRITICAL', 'WARNING'}:
            return finding
    return None


def _availability_finding_for(result: Dict[str, Any], components: Iterable[str]) -> Optional[Dict[str, Any]]:
    for finding in _matching_findings(result, components):
        if _status(finding.get('status')) == 'NO_EVALUABLE':
            return finding
    return None


def _load_finding_for(result: Dict[str, Any], component: str) -> Optional[Dict[str, Any]]:
    component = str(component or '').upper()
    direct = _actionable_finding_for(result, {component})
    if direct:
        return direct
    # Un hallazgo genérico STRESS_TEST sólo se atribuye al componente cuando la
    # evidencia lo nombra. Así un stop térmico de CPU no pinta también la GPU.
    for finding in _findings(result):
        if str(finding.get('component') or '').upper() != 'STRESS_TEST':
            continue
        haystack = ' '.join([
            str(finding.get('title') or ''),
            str(finding.get('explanation') or ''),
            *[str(x) for x in (finding.get('evidence') or [])],
        ]).upper()
        if component in haystack:
            return finding
    return None


def _metric(summary: Dict[str, Any], metric: str, field='max'):
    if not isinstance(summary, dict):
        return None
    block = summary.get(metric) if isinstance(summary.get(metric), dict) else {}
    return _num(block.get(field))


def _bench_status(item: Dict[str, Any]):
    raw = str((item or {}).get('status') or '').upper()
    if raw == 'OK':
        return 'MEDIDO'
    if raw in {'SAFETY_STOP', 'ERROR'}:
        return raw
    return 'N/A'


def _load_status(item, key):
    if item.get('status') == 'SAFETY_STOP':
        return 'PROTEGIDO'
    tele = item.get('telemetry') or {}
    throttle = (tele.get('throttling') or {}).get(key) or {}
    if throttle.get('state') in {'WATCHING', 'SUSPECTED', 'CONFIRMED'}:
        return 'REVISAR'
    metrics = {'cpu': ('cpu_usage', 'cpu_temp', 'cpu_ghz'),
               'gpu': ('gpu_usage', 'gpu_temp', 'gpu_clock_mhz'), 'ram': ('ram_usage',)}.get(key, ())
    available = bool(tele.get('during_sample_count')) and any(_metric(tele, m) is not None for m in metrics)
    return 'OBSERVADO' if available and item.get('status') == 'OK' else 'N/A'


def _component_state(finding, load_item, key):
    if finding:
        return _status(finding.get('status'))
    label = _load_status(load_item, key)
    # Una carga protegida no prueba que ese componente causó la parada.
    # La severidad térmica procede del hallazgo que identifica CPU/GPU.
    return {'OBSERVADO': 'NORMAL', 'REVISAR': 'WARNING'}.get(label, 'NO_EVALUABLE')


def _finding_summary(finding, fallback):
    return str((finding or {}).get('title') or fallback)


def _finding_reason(finding, fallback=''):
    text = str((finding or {}).get('explanation') or '').strip()
    return text or fallback


def _desktop_metric_available(result: Dict[str, Any], group: str, metrics: Iterable[str]) -> bool:
    """Confirma que la fase pasiva realmente produjo una métrica para el área.

    No convierte ausencia de alertas en "normal": sólo declara MEDIDO cuando
    existe al menos un valor numérico en las estadísticas congeladas de escritorio.
    """
    stats = result.get('statistics') if isinstance(result.get('statistics'), dict) else {}
    block = stats.get(group) if isinstance(stats.get(group), dict) else {}
    for metric in metrics:
        row = block.get(metric) if isinstance(block.get(metric), dict) else {}
        if any(_num(row.get(field)) is not None for field in ('avg', 'max', 'min', 'last')):
            return True
    return False


def _desktop_metric_value(result: Dict[str, Any], group: str, metric: str, field: str = 'avg'):
    stats = result.get('statistics') if isinstance(result.get('statistics'), dict) else {}
    block = stats.get(group) if isinstance(stats.get(group), dict) else {}
    row = block.get(metric) if isinstance(block.get(metric), dict) else {}
    return _num(row.get(field))


def _desktop_gpu_available(result: Dict[str, Any]) -> bool:
    stats = result.get('statistics') if isinstance(result.get('statistics'), dict) else {}
    gpus = stats.get('gpus') if isinstance(stats.get('gpus'), dict) else {}
    for row in gpus.values():
        if not isinstance(row, dict):
            continue
        for metric in ('usage_percent', 'temperature_c', 'core_clock_mhz'):
            value = row.get(metric) if isinstance(row.get(metric), dict) else {}
            if any(_num(value.get(field)) is not None for field in ('avg', 'max', 'min', 'last')):
                return True
    return False


def _desktop_gpu_summary(result: Dict[str, Any]) -> str | None:
    stats = result.get('statistics') if isinstance(result.get('statistics'), dict) else {}
    gpus = stats.get('gpus') if isinstance(stats.get('gpus'), dict) else {}
    measured = []
    for name, row in gpus.items():
        if not isinstance(row, dict):
            continue
        usage = _num((row.get('usage_percent') or {}).get('avg')) if isinstance(row.get('usage_percent'), dict) else None
        temp = _num((row.get('temperature_c') or {}).get('avg')) if isinstance(row.get('temperature_c'), dict) else None
        if usage is not None or temp is not None:
            measured.append((str(name), usage, temp))
    if len(measured) == 1:
        _, usage, temp = measured[0]
        parts = []
        if usage is not None:
            parts.append(f'{usage:.0f}% avg')
        if temp is not None:
            parts.append(f'{temp:.0f} °C avg')
        return 'Escritorio: ' + ' · '.join(parts) if parts else None
    if measured:
        return f'Escritorio: {len(measured)} GPU con telemetría'
    return None


def build_component_assessments(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Devuelve el informe vivo por componente sin crear scores nuevos."""
    result = result if isinstance(result, dict) else {}
    complete = result.get('complete_diagnostic') if isinstance(result.get('complete_diagnostic'), dict) else {}
    is_windows = str(complete.get('platform') or platform.system()).casefold() == 'windows'
    hardware = complete.get('hardware') if isinstance(complete.get('hardware'), dict) else {}
    windows = complete.get('windows') if isinstance(complete.get('windows'), dict) else {}
    benchmark = complete.get('benchmark') if isinstance(complete.get('benchmark'), dict) else {}
    load_components = benchmark
    load_title = 'Telemetría durante benchmark'

    reports: List[Dict[str, Any]] = []

    def add(key, title, status, summary, reason, evidence, facets, action_text):
        raw_facets = list(facets)[:3]
        clean_evidence = [str(x) for x in evidence if has_meaningful_value(x)][:3]
        reports.append({
            'key': key,
            'title': title,
            'status': _status(status),
            'summary': str(summary or 'Evidencia parcial'),
            'reason': str(reason or '').strip(),
            'evidence': clean_evidence,
            'facets': raw_facets,
            # V178: la UI conserva las tres facetas. Un N/A real no se oculta;
            # primero intentamos resolverlo desde las fuentes disponibles.
            'display_facets': raw_facets,
            'action_text': action_text,
        })

    # CPU
    cpu_load = load_components.get('cpu') if isinstance(load_components.get('cpu'), dict) else {}
    cpu_find = _load_finding_for(result, 'CPU')
    cpu_tele = cpu_load.get('telemetry') if isinstance(cpu_load.get('telemetry'), dict) else {}
    cpu_bench = benchmark.get('cpu') if isinstance(benchmark.get('cpu'), dict) else {}
    cpu_temp = _metric(cpu_tele, 'cpu_temp', 'max')
    cpu_usage = _metric(cpu_tele, 'cpu_usage', 'max')
    cpu_throughput = _num(cpu_bench.get('value'))
    cpu_state = _component_state(cpu_find, cpu_load, 'cpu')
    cpu_ev = []
    cpu_desktop_use = _desktop_metric_value(result, 'cpu', 'usage_percent', 'avg')
    cpu_desktop_temp = _desktop_metric_value(result, 'cpu', 'package_temp_c', 'avg')
    desktop_parts = []
    if cpu_desktop_use is not None: desktop_parts.append(f'{cpu_desktop_use:.0f}% avg')
    if cpu_desktop_temp is not None: desktop_parts.append(f'{cpu_desktop_temp:.0f} °C avg')
    if desktop_parts: cpu_ev.append('Escritorio: ' + ' · '.join(desktop_parts))
    load_parts = []
    if cpu_temp is not None: load_parts.append(f'{cpu_temp:.1f} °C máx.')
    if cpu_usage is not None: load_parts.append(f'{cpu_usage:.0f}% carga')
    if load_parts: cpu_ev.append('Durante benchmark: ' + ' · '.join(load_parts))
    if cpu_throughput is not None: cpu_ev.append(f'Benchmark {cpu_throughput:.0f} {cpu_bench.get("unit") or "MB/s"}')
    add('cpu', 'CPU', cpu_state,
        _finding_summary(cpu_find, 'Sin alertas observadas bajo carga' if cpu_state == 'NORMAL' else 'Evidencia parcial'),
        _finding_reason(cpu_find, 'Rendimiento y comportamiento observados durante la misma carga de benchmark; no certifica estabilidad prolongada.'), cpu_ev,
        [('Escritorio', 'MEDIDO' if _desktop_metric_available(result, 'cpu', ('usage_percent', 'package_temp_c', 'clock_avg_ghz')) else 'N/A', 'INFO' if _desktop_metric_available(result, 'cpu', ('usage_percent', 'package_temp_c', 'clock_avg_ghz')) else 'NO_EVALUABLE'),
         ('Benchmark', _bench_status(cpu_bench), 'INFO' if _bench_status(cpu_bench) == 'MEDIDO' else 'NO_EVALUABLE'),
         ('Bajo carga', _load_status(cpu_load, 'cpu'), cpu_state)],
        'Ver CPU')

    # GPU
    gpu_load = load_components.get('gpu') if isinstance(load_components.get('gpu'), dict) else {}
    gpu_find = _load_finding_for(result, 'GPU')
    gpu_tele = gpu_load.get('telemetry') if isinstance(gpu_load.get('telemetry'), dict) else {}
    gpu_bench = benchmark.get('gpu') if isinstance(benchmark.get('gpu'), dict) else {}
    gpu_temp = _metric(gpu_tele, 'gpu_temp', 'max')
    gpu_usage = _metric(gpu_tele, 'gpu_usage', 'max')
    gpu_value = _num(gpu_bench.get('value'))
    desktop_gpu = _desktop_gpu_available(result)
    # V181: la GPU se evalúa con benchmark real en ambas plataformas. En Linux
    # el proveedor es OpenGL/GLX visible; en Windows se conserva el benchmark
    # visual multiphase existente.
    gpu_state = _component_state(gpu_find, gpu_load, 'gpu') if gpu_bench else (_status(gpu_find.get('status')) if gpu_find else ('NORMAL' if desktop_gpu else 'NO_EVALUABLE'))
    gpu_ev = []
    gpu_desktop = _desktop_gpu_summary(result)
    if gpu_desktop: gpu_ev.append(gpu_desktop)
    load_parts = []
    if gpu_temp is not None: load_parts.append(f'{gpu_temp:.1f} °C máx.')
    if gpu_usage is not None: load_parts.append(f'{gpu_usage:.0f}% carga')
    if load_parts: gpu_ev.append('Durante benchmark: ' + ' · '.join(load_parts))
    if gpu_value is not None: gpu_ev.append(f'Benchmark {gpu_value:.1f} {gpu_bench.get("unit") or ""}'.strip())
    gpu_facets = [
        ('Escritorio', 'MEDIDO' if desktop_gpu else 'N/A', 'INFO' if desktop_gpu else 'NO_EVALUABLE'),
        ('Benchmark', _bench_status(gpu_bench), 'INFO' if _bench_status(gpu_bench) == 'MEDIDO' else 'NO_EVALUABLE'),
        ('Bajo carga', _load_status(gpu_load, 'gpu'), gpu_state),
    ]
    gpu_reason = 'Rendimiento y comportamiento observados durante la misma carga gráfica; no certifica estabilidad prolongada.'
    add('gpu', 'GPU', gpu_state,
        _finding_summary(gpu_find, 'GPU observada sin alertas en telemetría' if gpu_state == 'NORMAL' else 'Evidencia parcial'),
        _finding_reason(gpu_find, gpu_reason), gpu_ev, gpu_facets,
        'Ver GPU')

    # RAM
    ram_load = load_components.get('ram') if isinstance(load_components.get('ram'), dict) else {}
    ram_find = _actionable_finding_for(result, {'RAM'})
    ram_availability = _availability_finding_for(result, {'RAM'})
    ram_bench = benchmark.get('ram') if isinstance(benchmark.get('ram'), dict) else {}
    ram_state = _component_state(ram_find, ram_load, 'ram')
    if ram_state == 'NO_EVALUABLE' and ram_availability is not None:
        ram_find = ram_availability
    ram_value = _num(ram_bench.get('value'))
    ram_ev = []
    ram_desktop = _desktop_metric_value(result, 'ram', 'usage_percent', 'avg')
    if ram_desktop is not None: ram_ev.append(f'Escritorio: {ram_desktop:.0f}% uso avg')
    working = _metric(ram_load.get('telemetry') or {}, 'ram_usage')
    if working is not None: ram_ev.append(f'Durante benchmark: {working:.0f}% RAM máxima')
    if ram_value is not None:
        unit = str(ram_bench.get('unit') or '').strip()
        if unit.casefold() in {'mb/s', 'mib/s'}:
            ram_ev.append(f'Benchmark {ram_value / 1024.0:.2f} GB/s')
        else:
            ram_ev.append(f'Benchmark {ram_value:.2f} {unit}'.strip())
    add('ram', 'RAM', ram_state,
        _finding_summary(ram_find, 'Sin anomalías observadas durante benchmark' if ram_state == 'NORMAL' else 'Evidencia parcial'),
        _finding_reason(ram_find, 'El benchmark mide transferencia y registra el uso de RAM durante esa medición.'), ram_ev,
        [('Escritorio', 'MEDIDO' if _desktop_metric_available(result, 'ram', ('usage_percent',)) else 'N/A', 'INFO' if _desktop_metric_available(result, 'ram', ('usage_percent',)) else 'NO_EVALUABLE'),
         ('Benchmark', _bench_status(ram_bench), 'INFO' if _bench_status(ram_bench) == 'MEDIDO' else 'NO_EVALUABLE'),
         ('Bajo carga', _load_status(ram_load, 'ram'), ram_state)],
        'Ver RAM')

    # Almacenamiento. Salud y benchmark son dimensiones separadas.
    storage_find = _actionable_finding_for(result, {'STORAGE', 'DISK', 'SSD', 'NVME'})
    storage_matches = _matching_findings(result, {'STORAGE', 'DISK', 'SSD', 'NVME'})
    disks = hardware.get('storage') if isinstance(hardware.get('storage'), list) else []
    ssd_bench = benchmark.get('ssd') if isinstance(benchmark.get('ssd'), dict) else {}
    life_values = []
    temps = []
    for disk in disks:
        if not isinstance(disk, dict):
            continue
        life = physical_health(disk)
        if life is not None: life_values.append(life)
        temp = _num(disk.get('temperature_c'))
        if temp is not None: temps.append(temp)
    if storage_find:
        storage_state = _status(storage_find.get('status'))
    elif any(_status(x.get('status')) == 'NO_EVALUABLE' for x in storage_matches):
        # Si alguna unidad quedó sin evidencia, el resumen global no puede decir
        # que todo el almacenamiento quedó sin alertas.
        storage_state = 'NO_EVALUABLE'
    elif any(_status(x.get('status')) == 'NORMAL' for x in storage_matches) or life_values:
        # 'SIN ALERTAS' describe lo observado; la faceta Salud permanece N/A
        # cuando no existe porcentaje físico verificable.
        storage_state = 'NORMAL'
    else:
        storage_state = 'NO_EVALUABLE'
    if storage_find:
        storage_summary = _finding_summary(storage_find, 'Revisar almacenamiento')
    elif life_values:
        storage_summary = 'Salud física reportada por al menos una unidad'
    elif disks:
        storage_summary = 'Unidades detectadas; salud física no disponible'
    else:
        storage_summary = 'Almacenamiento no evaluable'
    storage_ev = []
    if life_values: storage_ev.append(f'Vida reportada mín. {min(life_values):.0f}%')
    elif temps: storage_ev.append(f'Temperatura máx. {max(temps):.1f} °C · salud física N/A')
    read_mbps = _num(ssd_bench.get('read_mbps')); write_mbps = _num(ssd_bench.get('write_mbps'))
    if read_mbps is not None: storage_ev.append(f'Lectura benchmark {read_mbps:.0f} MB/s')
    elif write_mbps is not None: storage_ev.append(f'Escritura benchmark {write_mbps:.0f} MB/s')
    health_facet = f'{min(life_values):.0f}%' if life_values else 'N/A'
    usage_values = [_num(disk.get('used_space_percent', disk.get('used_percent'))) for disk in disks if isinstance(disk, dict)]
    usage_values = [value for value in usage_values if value is not None]
    usage_facet = f'{max(usage_values):.0f}%' if usage_values else 'N/A'
    if usage_values:
        insert_at = 1 if storage_ev else 0
        storage_ev.insert(insert_at, f'Espacio utilizado máx. {max(usage_values):.0f}%')
    add('storage', 'Almacenamiento', storage_state, storage_summary,
        _finding_reason(storage_find, 'La salud física no se infiere desde el benchmark.'), storage_ev,
        [('Salud', health_facet, 'NORMAL' if life_values else 'NO_EVALUABLE'),
         ('Espacio', usage_facet, 'INFO' if usage_values else 'NO_EVALUABLE'),
         ('Benchmark', _bench_status(ssd_bench), 'INFO' if _bench_status(ssd_bench) == 'MEDIDO' else 'NO_EVALUABLE')],
        'Ver almacenamiento')

    # Batería
    battery = hardware.get('battery') if isinstance(hardware.get('battery'), dict) else {}
    battery_find = _actionable_finding_for(result, {'BATTERY', 'BATERIA', 'BATERÍA'})
    present = battery.get('present')
    health = _num(battery.get('health_percent'))
    wear = _num(battery.get('wear_percent'))
    if wear is None: wear = _num(battery.get('degradation_percent'))
    cycles = _num(battery.get('cycle_count'))
    if present is False:
        batt_state, batt_summary = 'INFO', 'No aplica en este equipo'
    elif battery_find:
        batt_state, batt_summary = _status(battery_find.get('status')), _finding_summary(battery_find, 'Revisar batería')
    elif health is not None or wear is not None:
        batt_state, batt_summary = 'INFO', 'Salud de batería medida'
    elif present is True:
        batt_state, batt_summary = 'NO_EVALUABLE', 'Batería presente; salud no disponible'
    else:
        batt_state, batt_summary = 'NO_EVALUABLE', 'Batería no evaluable'
    batt_ev = []
    if health is not None: batt_ev.append(f'Capacidad conservada {health:.0f}%')
    if wear is not None: batt_ev.append(f'Desgaste {wear:.0f}%')
    if cycles is not None: batt_ev.append(f'{cycles:.0f} ciclos')
    add('battery', 'Batería', batt_state, batt_summary,
        _finding_reason(battery_find, 'La batería se evalúa por capacidad/desgaste cuando el firmware lo expone.'), batt_ev,
        [('Salud', f'{health:.0f}%' if health is not None else 'N/A', 'NORMAL' if health is not None else 'NO_EVALUABLE'),
         ('Desgaste', f'{wear:.0f}%' if wear is not None else 'N/A', 'INFO' if wear is not None else 'NO_EVALUABLE'),
         ('Ciclos', f'{cycles:.0f}' if cycles is not None else 'N/A', 'INFO' if cycles is not None else 'NO_EVALUABLE')],
        'Ver batería')

    # Windows sólo forma parte del diagnóstico en Windows.
    if is_windows:
        # Windows
        windows_find = _finding_for(result, {'WINDOWS', 'WINDOWS_STARTUP', 'DRIVERS'})
        windows_partial = any(not isinstance(windows.get(k), dict) or not windows[k] or windows[k].get('error')
                              for k in ('startup', 'services', 'stability', 'drivers'))
        windows_partial = bool(windows_partial or str((windows.get('stability') or {}).get('severity') or '').upper() in {'', 'NO_EVALUABLE', 'UNKNOWN'})
        windows_state = _status((windows_find or {}).get('status'), 'NO_EVALUABLE' if windows_partial else 'NORMAL') if windows else 'NO_EVALUABLE'
        windows_summary = _finding_summary(windows_find, 'Windows parcialmente evaluable' if windows_partial else 'Sin hallazgos prioritarios en Windows' if windows else 'Windows no evaluable')
        drivers = windows.get('drivers') if isinstance(windows.get('drivers'), dict) else {}
        startup = windows.get('startup') if isinstance(windows.get('startup'), dict) else {}
        stability = windows.get('stability') if isinstance(windows.get('stability'), dict) else {}
        problems = int(drivers.get('device_problems') or 0)
        degraded = [x for x in (startup.get('items') or []) if isinstance(x, dict) and x.get('degradation_event_seen')]
        severity = str(stability.get('severity') or '').upper()
        win_ev = []
        if problems: win_ev.append(f'{problems} dispositivo(s) con problema')
        if degraded: win_ev.append(f'{len(degraded)} entrada(s) de inicio con degradación')
        if severity and severity not in {'NORMAL', 'OK', 'NONE', 'NO_EVALUABLE'}: win_ev.append(f'Estabilidad: {severity}')
        if not win_ev and startup.get('count') is not None: win_ev.append(f'{startup.get("count")} entradas de inicio analizadas')
        stability_value = 'OK' if severity in {'NORMAL', 'OK', 'NONE'} else 'N/A' if not severity or severity == 'NO_EVALUABLE' else severity
        driver_value = f'{problems} PROB.' if problems else ('OK' if drivers and not drivers.get('error') else 'N/A')
        startup_value = f'{len(degraded)} REVISAR' if degraded else ('OK' if startup and not startup.get('error') else 'N/A')
        add('windows', 'Windows', windows_state, windows_summary,
            _finding_reason(windows_find, 'Inicio, estabilidad y controladores se analizan sin aplicar reparaciones.'), win_ev,
            [('Estabilidad', stability_value, 'NORMAL' if stability_value == 'OK' else 'WARNING' if stability_value not in {'N/A'} else 'NO_EVALUABLE'),
             ('Drivers', driver_value, 'WARNING' if problems else 'NORMAL' if driver_value == 'OK' else 'NO_EVALUABLE'),
             ('Inicio', startup_value, 'WARNING' if degraded else 'NORMAL' if startup_value == 'OK' else 'NO_EVALUABLE')],
            'Revisar Windows')


    from core.audio_test import empty_result, evidence_rows, summary
    audio = result.get('audio_test') or empty_result()
    mode = str(audio.get('mode') or '').upper()
    tech = audio.get('technical') if isinstance(audio.get('technical'), dict) else {}
    devices = audio.get('devices') if isinstance(audio.get('devices'), dict) else {}
    errors = [str(x) for x in (audio.get('errors') or []) if str(x).strip()]
    if mode == 'AUTOMATIC_TECHNICAL':
        left_ok = bool((tech.get('left') or {}).get('api_completed'))
        right_ok = bool((tech.get('right') or {}).get('api_completed'))
        both_ok = bool((tech.get('both') or {}).get('api_completed'))
        capture_ok = bool((tech.get('capture') or {}).get('completed'))
        output_ok = left_ok and right_ok and both_ok
        if output_ok and capture_ok:
            audio_state, audio_status = 'NORMAL', 'Prueba técnica automática completada'
        elif output_ok or capture_ok:
            audio_state, audio_status = 'NO_EVALUABLE', 'Verificación técnica parcial'
        else:
            audio_state, audio_status = 'WARNING', 'No se pudo verificar la ruta de audio'
        out_name = str((devices.get('output') or {}).get('name') or 'N/A')
        in_name = str((devices.get('input') or {}).get('name') or 'N/A')
        audio_ev = []
        if errors:
            audio_ev.extend(errors[:3])
        add('audio', 'Audio', audio_state, audio_status,
            'Prueba automática de reproducción estéreo y apertura del stream de micrófono. La confirmación humana sigue disponible como comprobación acústica opcional.',
            audio_ev,
            [('Izquierdo', 'OK' if left_ok else 'FALLO', 'NORMAL' if left_ok else 'WARNING'),
             ('Derecho', 'OK' if right_ok else 'FALLO', 'NORMAL' if right_ok else 'WARNING'),
             ('Micrófono', 'OK' if capture_ok else 'FALLO', 'NORMAL' if capture_ok else 'WARNING')],
            'Abrir Test de Audio')
    else:
        answers = audio.get('answers', {})
        audio_status = summary(audio)
        audio_state = 'WARNING' if audio_status == 'PROBLEMA REPORTADO' else 'NORMAL' if audio_status == 'AUDIO VERIFICADO' else 'NO_EVALUABLE'
        add('audio', 'Audio', audio_state, audio_status,
            'Confirmación humana de una prueba local reciente.',
            [f'{k}: {v}' for k, v in evidence_rows(audio) if k in ('Canal izquierdo', 'Canal derecho', 'Reproducción del micrófono')],
            [(label, answers.get(key, 'NO EVALUADO'), 'NORMAL' if answers.get(key) == 'VERIFICADO' else 'WARNING' if answers.get(key) == 'PROBLEMA REPORTADO' else 'NO_EVALUABLE')
             for label, key in (('Izquierdo', 'left'), ('Derecho', 'right'), ('Micrófono', 'microphone'))],
            'Abrir Test de Audio')

    return reports



def _fmt_metric(value, digits=1, suffix=''):
    number = _num(value)
    if number is None:
        return 'N/A'
    return f'{number:.{digits}f}{suffix}'


def _stat_metric(result: Dict[str, Any], group: str, metric: str, field: str = 'avg'):
    stats = result.get('statistics') if isinstance(result.get('statistics'), dict) else {}
    block = stats.get(group) if isinstance(stats.get(group), dict) else {}
    metric_block = block.get(metric) if isinstance(block.get(metric), dict) else {}
    return _num(metric_block.get(field))


def _load_throttling_label(component: Dict[str, Any], key: str) -> str:
    telemetry = component.get('telemetry') if isinstance(component.get('telemetry'), dict) else {}
    throttling = telemetry.get('throttling') if isinstance(telemetry.get('throttling'), dict) else {}
    state = throttling.get(key) if isinstance(throttling.get(key), dict) else {}
    raw = str(state.get('state') or state.get('status') or '').strip()
    return {'CONFIRMED': 'Detectado (sensor explícito)', 'SUSPECTED': 'Posible limitación; throttling no confirmado', 'WATCHING': 'Margen térmico reducido; throttling no confirmado', 'NO_EVIDENCE': 'No observado con la evidencia disponible'}.get(raw, 'N/A')


def _section(title: str, rows: Iterable[tuple[str, Any]], *, note: str = '') -> Dict[str, Any]:
    clean = []
    for label, value in rows:
        text = str(value if value not in (None, '') else 'N/A')
        clean.append({'label': str(label), 'value': text})
    return {'title': str(title), 'rows': clean, 'note': str(note or '')}


def build_component_evidence(result: Dict[str, Any], key: str) -> Dict[str, Any]:
    """Expone la evidencia trazable usada por el Diagnóstico Completo.

    No crea puntuaciones ni infiere métricas ausentes. La salida está pensada
    para UI/PDF y conserva N/A cuando el proveedor no expuso el dato.
    """
    result = result if isinstance(result, dict) else {}
    key = str(key or '').lower()
    assessments = {x.get('key'): x for x in build_component_assessments(result)}
    report = assessments.get(key) or {'key': key, 'title': key.upper(), 'status': 'NO_EVALUABLE', 'summary': 'Evidencia no disponible', 'reason': ''}
    complete = result.get('complete_diagnostic') if isinstance(result.get('complete_diagnostic'), dict) else {}
    is_windows = str(complete.get('platform') or platform.system()).casefold() == 'windows'
    hardware = complete.get('hardware') if isinstance(complete.get('hardware'), dict) else {}
    windows = complete.get('windows') if isinstance(complete.get('windows'), dict) else {}
    benchmark = complete.get('benchmark') if isinstance(complete.get('benchmark'), dict) else {}
    load_components = benchmark
    load_title = 'Telemetría durante benchmark'
    sections: List[Dict[str, Any]] = []

    if key == 'audio':
        from core.audio_test import evidence_rows
        sections.append(_section('Test de Audio · confirmación manual', evidence_rows(result.get('audio_test')),
                                 note='Válido durante 24 horas y para los mismos dispositivos predeterminados. No certifica calidad ni salud de audio.'))

    elif key == 'cpu':
        item = load_components.get('cpu') if isinstance(load_components.get('cpu'), dict) else {}
        tele = item.get('telemetry') if isinstance(item.get('telemetry'), dict) else {}
        bench = benchmark.get('cpu') if isinstance(benchmark.get('cpu'), dict) else {}
        sections.append(_section('Escritorio', [
            ('Uso promedio', _fmt_metric(_stat_metric(result, 'cpu', 'usage_percent', 'avg'), 1, '%')),
            ('Uso máximo', _fmt_metric(_stat_metric(result, 'cpu', 'usage_percent', 'max'), 1, '%')),
            ('Temperatura promedio', _fmt_metric(_stat_metric(result, 'cpu', 'package_temp_c', 'avg'), 1, ' °C')),
            ('Temperatura máxima', _fmt_metric(_stat_metric(result, 'cpu', 'package_temp_c', 'max'), 1, ' °C')),
            ('Frecuencia promedio', _fmt_metric(_stat_metric(result, 'cpu', 'clock_avg_ghz', 'avg'), 2, ' GHz')),
            ('Distancia mínima a TjMax', _fmt_metric(_stat_metric(result, 'cpu', 'distance_to_tjmax_min_c', 'min'), 1, ' °C')),
        ]))
        sections.append(_section(load_title, [
            ('Estado', str(item.get('status') or 'N/A').upper()),
            ('Duración', _fmt_metric(item.get('duration_s'), 1, ' s')),
            ('Carga máxima', _fmt_metric(_metric(tele, 'cpu_usage', 'max'), 1, '%')),
            ('Temperatura máxima', _fmt_metric(_metric(tele, 'cpu_temp', 'max'), 1, ' °C')),
            ('Frecuencia mínima', _fmt_metric(_metric(tele, 'cpu_ghz', 'min'), 2, ' GHz')),
            ('Frecuencia máxima', _fmt_metric(_metric(tele, 'cpu_ghz', 'max'), 2, ' GHz')),
            ('Throttling', _load_throttling_label(item, 'cpu')),
            ('Errores de ejecución', '; '.join(tele.get('execution_errors') or []) or ('No observados' if item.get('status') == 'OK' else str(item.get('reason') or 'N/A'))),
        ], note=str(item.get('reason') or 'Observación durante la medición; no certifica estabilidad prolongada.')))
        sections.append(_section('Benchmark', [
            ('Estado', str(bench.get('status') or 'N/A').upper()),
            ('Resultado', f"{_fmt_metric(bench.get('value'), 1)} {str(bench.get('unit') or '').strip()}".strip()),
            ('Duración', _fmt_metric(bench.get('duration_s'), 1, ' s')),
            ('Transferencia SHA-256', _fmt_metric(bench.get('throughput_mbps'), 1, ' MB/s')),
            ('Proveedor', str(bench.get('provider') or 'N/A')),
        ], note='Rendimiento medido localmente; CorePulse no usa ranking externo.'))

    elif key == 'gpu':
        item = load_components.get('gpu') if isinstance(load_components.get('gpu'), dict) else {}
        tele = item.get('telemetry') if isinstance(item.get('telemetry'), dict) else {}
        bench = benchmark.get('gpu') if isinstance(benchmark.get('gpu'), dict) else {}
        stats = result.get('statistics') if isinstance(result.get('statistics'), dict) else {}
        gpu_stats = stats.get('gpus') if isinstance(stats.get('gpus'), dict) else {}
        renderer = str(bench.get('renderer') or item.get('renderer') or '').strip().casefold()
        matching = [(name, row) for name, row in gpu_stats.items() if renderer and str(name).strip().casefold() == renderer]
        gpu_name, gpu_row = matching[0] if len(matching) == 1 else next(iter(gpu_stats.items()), ('N/A', {}))
        gpu_row = gpu_row if isinstance(gpu_row, dict) else {}
        sections.append(_section('Escritorio', [
            ('GPU observada', gpu_name),
            ('Adaptadores observados', ', '.join(str(name) for name in gpu_stats) or 'N/A'),
            ('Frecuencia promedio', _fmt_metric(((gpu_row.get('core_clock_mhz') or {}).get('avg') if isinstance(gpu_row.get('core_clock_mhz'), dict) else None), 0, ' MHz')),
            ('Uso promedio', _fmt_metric(((gpu_row.get('usage_percent') or {}).get('avg') if isinstance(gpu_row.get('usage_percent'), dict) else None), 1, '%')),
            ('Uso máximo', _fmt_metric(((gpu_row.get('usage_percent') or {}).get('max') if isinstance(gpu_row.get('usage_percent'), dict) else None), 1, '%')),
            ('Temperatura promedio', _fmt_metric(((gpu_row.get('temperature_c') or {}).get('avg') if isinstance(gpu_row.get('temperature_c'), dict) else None), 1, ' °C')),
            ('Temperatura máxima', _fmt_metric(((gpu_row.get('temperature_c') or {}).get('max') if isinstance(gpu_row.get('temperature_c'), dict) else None), 1, ' °C')),
        ]))
        if is_windows:
            sections.append(_section(load_title, [
                ('Estado', str(item.get('status') or 'N/A').upper()),
                ('Duración', _fmt_metric(item.get('duration_s'), 1, ' s')),
                ('Carga máxima', _fmt_metric(_metric(tele, 'gpu_usage', 'max'), 1, '%')),
                ('Temperatura máxima', _fmt_metric(_metric(tele, 'gpu_temp', 'max'), 1, ' °C')),
                ('Renderer', str(item.get('renderer') or 'N/A')),
                ('Frecuencia mínima', _fmt_metric(_metric(tele, 'gpu_clock_mhz', 'min'), 0, ' MHz')),
                ('Frecuencia máxima', _fmt_metric(_metric(tele, 'gpu_clock_mhz', 'max'), 0, ' MHz')),
                ('Throttling', _load_throttling_label(item, 'gpu')),
                ('Errores de ejecución', '; '.join(tele.get('execution_errors') or []) or ('No observados' if item.get('status') == 'OK' else str(item.get('reason') or 'N/A'))),
            ], note=str(item.get('reason') or 'Sensores enlazados al renderer del benchmark; N/A si no existe coincidencia verificable.')))
            sections.append(_section('Benchmark', [
                ('Estado', str(bench.get('status') or 'N/A').upper()),
                ('Resultado', f"{_fmt_metric(bench.get('value'), 1)} {str(bench.get('unit') or '').strip()}".strip()),
                ('Fases', str(bench.get('phases') or bench.get('phase_results') or 'N/A')),
                ('FPS de la carga', _fmt_metric(bench.get('frames_per_s'), 1, ' FPS')),
                ('1% low de la carga', _fmt_metric(bench.get('fps_1pct_low'), 1, ' FPS')),
                ('Renderer', str(bench.get('renderer') or 'N/A')),
                ('Duración', _fmt_metric(bench.get('duration_s'), 1, ' s')),
            ], note='Rendimiento medido por la carga OpenGL de CorePulse; no equivale a FPS de un juego.'))

    elif key == 'ram':
        snapshot = hardware.get('telemetry_snapshot') or {}
        item = load_components.get('ram') if isinstance(load_components.get('ram'), dict) else {}
        bench = benchmark.get('ram') if isinstance(benchmark.get('ram'), dict) else {}
        sections.append(_section('Escritorio', [
            ('Capacidad', _fmt_metric(snapshot.get('ram_total_gb'), 2, ' GB')),
            ('Uso promedio', _fmt_metric(_stat_metric(result, 'ram', 'usage_percent', 'avg'), 1, '%')),
            ('Uso máximo', _fmt_metric(_stat_metric(result, 'ram', 'usage_percent', 'max'), 1, '%')),
            ('Tiempo ≥85%', _fmt_metric(((result.get('statistics') or {}).get('ram') or {}).get('seconds_over_85_percent'), 0, ' s')),
            ('Tiempo ≥95%', _fmt_metric(((result.get('statistics') or {}).get('ram') or {}).get('seconds_over_95_percent'), 0, ' s')),
        ]))
        sections.append(_section(load_title, [
            ('Estado', str(item.get('status') or 'N/A').upper()),
            ('Duración', _fmt_metric(item.get('duration_s'), 1, ' s')),
            ('Uso máximo RAM', _fmt_metric(_metric(item.get('telemetry') or {}, 'ram_usage'), 1, '%')),
            ('Proveedor', str(item.get('provider') or 'N/A')),
        ], note=str(item.get('reason') or 'Uso de memoria observado durante el benchmark de copia sostenida.')))
        value = _num(bench.get('value'))
        unit = str(bench.get('unit') or '').strip()
        if value is not None and unit.casefold() in {'mb/s', 'mib/s'}:
            bench_value = f'{value / 1024.0:.2f} GB/s'
        else:
            bench_value = f"{_fmt_metric(value, 2)} {unit}".strip()
        sections.append(_section('Benchmark', [
            ('Estado', str(bench.get('status') or 'N/A').upper()),
            ('Tasa de copia sostenida', bench_value),
            ('Duración', _fmt_metric(bench.get('duration_s'), 1, ' s')),
            ('Proveedor', str(bench.get('provider') or 'N/A')),
        ]))

    elif key == 'storage':
        drives = hardware.get('storage') if isinstance(hardware.get('storage'), list) else []
        storage_stats = (result.get('statistics') or {}).get('storage') if isinstance((result.get('statistics') or {}).get('storage'), dict) else {}
        health_rows = []
        for idx, drive in enumerate(drives, 1):
            if not isinstance(drive, dict):
                continue
            name = str(drive.get('name') or drive.get('model') or f'Unidad {idx}')
            life = physical_health(drive)
            temp = _num(drive.get('temperature_c'))
            source = str(drive.get('health_source') or drive.get('source') or '').strip()
            value = f"Salud {_fmt_metric(life, 0, '%')} · Temp {_fmt_metric(temp, 0, ' °C')}"
            if source:
                value += f' · {source}'
            health_rows.append((name, value))
            health_rows.extend([
                ('Disco físico', drive.get('physical_disk_index')),
                ('Volúmenes', drive.get('mount_points')),
                ('Estado del sistema', drive.get('windows_health_status')),
                ('Fuente de salud', source or 'N/A'),
                ('Desgaste', _fmt_metric(drive.get('wear_percent') if drive.get('wear_quantitative_reliable') else None, 0, '%')),
                ('Espacio utilizado', _fmt_metric(drive.get('used_space_percent', drive.get('used_percent')), 1, '%')),
            ])
        if not health_rows:
            for name, row in list(storage_stats.items())[:4]:
                row = row if isinstance(row, dict) else {}
                temp_block = row.get('temperature_c') if isinstance(row.get('temperature_c'), dict) else {}
                health_rows.append((str(name), f"Salud {_fmt_metric(row.get('life_percent'), 0, '%')} · Temp {_fmt_metric(temp_block.get('max'), 0, ' °C')}"))
        sections.append(_section('Salud física', health_rows or [('Unidades', 'N/A')], note='La salud física sólo se muestra cuando una fuente real expone desgaste/vida útil.'))
        bench = benchmark.get('ssd') if isinstance(benchmark.get('ssd'), dict) else {}
        sections.append(_section('Benchmark SSD', [
            ('Estado', str(bench.get('status') or 'N/A').upper()),
            ('Volumen probado', str(bench.get('path_root') or 'N/A')),
            ('Lectura secuencial', _fmt_metric(bench.get('read_mbps'), 0, ' MB/s')),
            ('Escritura secuencial', _fmt_metric(bench.get('write_mbps'), 0, ' MB/s')),
            ('Archivo de prueba', _fmt_metric(bench.get('size_mb'), 0, ' MB')),
            ('Modo E/S', str(bench.get('io_mode') or 'N/A')),
            ('Resistente a caché', 'Sí' if bench.get('cache_resistant') is True else 'No / fallback' if bench.get('cache_resistant') is False else 'N/A'),
            ('Duración', _fmt_metric(bench.get('duration_s'), 1, ' s')),
        ], note=('El benchmark mide únicamente el volumen indicado. En Windows intenta I/O directo; si no está disponible, el fallback puede usar caché. En Linux usa el método compatible de la plataforma. No determina por sí solo la salud física.')))

        tele = bench.get('telemetry') or {}
        sections.append(_section('Telemetría durante benchmark', [
            ('Unidad monitorizada', ', '.join(tele.get('storage_names') or []) or 'N/A'),
            ('Volumen probado', bench.get('path_root')),
            ('Temperatura inicial', _fmt_metric(_metric(tele, 'storage_temperature', 'initial'), 1, ' °C')),
            ('Temperatura máxima', _fmt_metric(_metric(tele, 'storage_temperature', 'max'), 1, ' °C')),
        ], note='Sólo sensores de la unidad enlazada al volumen probado; N/A si no se puede verificar.'))

    elif key == 'battery':
        battery = hardware.get('battery') if isinstance(hardware.get('battery'), dict) else {}
        present = battery.get('present')
        sections.append(_section('Batería', [
            ('Presente', 'Sí' if present is True else 'No' if present is False else 'N/A'),
            ('Capacidad conservada', _fmt_metric(battery.get('health_percent'), 0, '%')),
            ('Desgaste', _fmt_metric(battery.get('wear_percent') if battery.get('wear_percent') is not None else battery.get('degradation_percent'), 0, '%')),
            ('Ciclos', _fmt_metric(battery.get('cycle_count'), 0)),
            ('Capacidad de diseño', _fmt_metric(battery.get('designed_capacity_mwh'), 0, ' mWh')),
            ('Carga completa actual', _fmt_metric(battery.get('full_charge_capacity_mwh'), 0, ' mWh')),
        ], note='CorePulse conserva N/A cuando ACPI/firmware no expone capacidad o ciclos.'))

    elif key == 'windows':
        startup = windows.get('startup') if isinstance(windows.get('startup'), dict) else {}
        services = windows.get('services') if isinstance(windows.get('services'), dict) else {}
        stability = windows.get('stability') if isinstance(windows.get('stability'), dict) else {}
        drivers = windows.get('drivers') if isinstance(windows.get('drivers'), dict) else {}
        degraded = [x for x in (startup.get('items') or []) if isinstance(x, dict) and x.get('degradation_event_seen')]
        sections.append(_section('Inicio', [
            ('Entradas analizadas', startup.get('count') if startup.get('count') is not None else 'N/A'),
            ('Con degradación observada', len(degraded) if startup and not startup.get('error') else 'N/A'),
            ('Estado del análisis', 'ERROR' if startup.get('error') else 'OK' if startup else 'N/A'),
        ]))
        sections.append(_section('Servicios y estabilidad', [
            ('Servicios analizados', services.get('count') if services.get('count') is not None else 'N/A'),
            ('Estado servicios', 'ERROR' if services.get('error') else 'OK' if services else 'N/A'),
            ('Severidad estabilidad', str(stability.get('severity') or 'N/A')),
            ('Estado estabilidad', 'ERROR' if stability.get('error') else 'OK' if stability else 'N/A'),
        ]))
        sections.append(_section('Controladores', [
            ('Dispositivos con problema', drivers.get('device_problems') if drivers.get('device_problems') is not None else 'N/A'),
            ('Dispositivos analizados', drivers.get('count') if drivers.get('count') is not None else 'N/A'),
            ('Estado del análisis', 'ERROR' if drivers.get('error') else 'OK' if drivers else 'N/A'),
        ], note='El diagnóstico analiza; no instala, elimina ni repara controladores automáticamente.'))

    findings = _matching_findings(result, {key.upper(), 'DRIVERS' if key == 'windows' else key.upper(), 'WINDOWS_STARTUP' if key == 'windows' else key.upper()})
    finding_rows = []
    for finding in findings[:4]:
        finding_rows.append((str(finding.get('title') or 'Hallazgo'), str(finding.get('explanation') or 'Sin explicación adicional')))
        for evidence in (finding.get('evidence') or [])[:2]:
            finding_rows.append(('Evidencia', str(evidence)))
    if finding_rows:
        sections.append(_section('Hallazgos que influyeron', finding_rows))

    comparison = complete.get('comparison') if isinstance(complete.get('comparison'), dict) else {}
    if comparison.get('available'):
        change = next((x for x in (comparison.get('component_changes') or []) if isinstance(x, dict) and str(x.get('key') or '').lower() == key), None)
        if change:
            sections.append(_section('Comparación anterior', [
                ('Estado anterior', str(change.get('previous') or 'N/A').replace('_', ' ')),
                ('Estado actual', str(change.get('current') or 'N/A').replace('_', ' ')),
            ], note='Comparación informativa; el historial no se usa como fuente de fallos del diagnóstico actual.'))
        else:
            sections.append(_section('Comparación anterior', [
                ('Cambio de estado', 'Sin cambios'),
            ], note='Comparación informativa; el diagnóstico actual depende sólo de su evidencia presente.'))

    # V177: el detalle visual sólo contiene evidencia que realmente existe.
    # REAL_OR_NA sigue vigente en los datos originales; aquí únicamente se
    # evita presentar filas vacías como si fueran evidencia.
    clean_sections = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        clean_rows = []
        for row in (section.get('rows') or []):
            if not isinstance(row, dict):
                continue
            if has_meaningful_value(row.get('value')):
                clean_rows.append(row)
        if clean_rows:
            clean = dict(section)
            clean['rows'] = clean_rows
            clean_sections.append(clean)

    order = {'Escritorio': 0, 'Salud física': 0, 'Benchmark': 1, 'Benchmark SSD': 1,
             'Telemetría durante benchmark': 2}
    clean_sections.sort(key=lambda section: order.get(section['title'], 3))
    return {
        'key': key,
        'title': str(report.get('title') or key.upper()),
        'status': _status(report.get('status')),
        'summary': str(report.get('summary') or 'Evidencia parcial'),
        'reason': str(report.get('reason') or ''),
        'sections': clean_sections,
        'has_evidence': bool(clean_sections),
        'policy': 'REAL_OR_NA',
    }

def build_diagnostic_overview(result: Dict[str, Any]) -> Dict[str, Any]:
    """Resumen integral y trazable para pantalla/PDF.

    Cuenta estados ya existentes; no crea scores ni transforma N/A en salud.
    """
    reports = build_component_assessments(result if isinstance(result, dict) else {})
    counts = {key: 0 for key in ('CRITICAL', 'WARNING', 'NORMAL', 'NO_EVALUABLE', 'INFO')}
    for report in reports:
        counts[_status(report.get('status'))] += 1

    complete = result.get('complete_diagnostic') if isinstance(result, dict) and isinstance(result.get('complete_diagnostic'), dict) else {}
    coverage = complete.get('phase_coverage') if isinstance(complete.get('phase_coverage'), dict) else {}
    completed = int(coverage.get('completed') or 0)
    total_phases = int(coverage.get('total') or 0)
    attention = counts['CRITICAL'] + counts['WARNING']
    measured_or_applicable = len(reports) - counts['NO_EVALUABLE']

    if counts['CRITICAL']:
        summary = f"{counts['CRITICAL']} área(s) crítica(s) y {counts['WARNING']} para revisar."
    elif counts['WARNING']:
        summary = f"{counts['WARNING']} área(s) requieren revisión con evidencia actual."
    elif counts['NO_EVALUABLE']:
        summary = f"Sin alertas prioritarias en lo evaluable; {counts['NO_EVALUABLE']} área(s) quedaron con medición parcial."
    else:
        summary = 'Sin acciones prioritarias detectadas en las áreas evaluadas.'

    phase_text = f'{completed}/{total_phases} fases' if total_phases else 'Cobertura de fases no disponible'
    headline = f'{measured_or_applicable}/{len(reports)} áreas con resultado · {attention} requieren atención · {phase_text}'
    return {
        'total_areas': len(reports),
        'areas_with_result': measured_or_applicable,
        'attention_count': attention,
        'critical_count': counts['CRITICAL'],
        'warning_count': counts['WARNING'],
        'na_count': counts['NO_EVALUABLE'],
        'informational_count': counts['INFO'],
        'normal_count': counts['NORMAL'],
        'completed_phases': completed,
        'total_phases': total_phases,
        'partial': bool(coverage.get('partial') or counts['NO_EVALUABLE']),
        'headline': headline,
        'summary': summary,
        'policy': 'COUNTS_ONLY_FROM_REAL_COMPONENT_ASSESSMENTS',
    }


def select_priority_assessment(reports: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Elige la primera acción realmente prioritaria sin inventar severidad."""
    rows = [x for x in reports if isinstance(x, dict)]
    for level in ('CRITICAL', 'WARNING'):
        for report in rows:
            if _status(report.get('status')) == level:
                return report
    return None
