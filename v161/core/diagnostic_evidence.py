"""Adaptadores puros de evidencia existente; no consultan ni simulan sensores."""
import copy
import math


def number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def physical_health(drive):
    for key in ('health_percent', 'life_percent', 'health'):
        value = number(drive.get(key))
        if value is not None and 0 <= value <= 100:
            return value
    return None


def storage_snapshot(telemetry, volumes):
    devices = telemetry.get('_storage_devices') or []
    cache = telemetry.get('_storage_health_cache') or {}
    output = []
    for index, device in enumerate(devices):
        if not isinstance(device, dict):
            continue
        row = copy.deepcopy(device)
        cached = cache.get(index, cache.get(str(index), {}))
        name = str(device.get('model') or device.get('name') or '').strip().casefold()
        cached_name = str(cached.get('model') or '').strip().casefold()
        # No asignar salud de otro dispositivo sólo por posición en la lista.
        if name and name == cached_name:
            row.update(copy.deepcopy(cached))
            row['health_percent'] = cached.get('health')
            row['life_percent'] = cached.get('health')
        output.append(row)
    return output or copy.deepcopy(volumes)


def active_gpu(gpus):
    """Mayor actividad medida; un empate o uso cero no prueba qué GPU ejecuta la carga."""
    candidates = [g for g in gpus if isinstance(g, dict) and number(g.get('usage_percent')) is not None]
    candidates.sort(key=lambda g: number(g['usage_percent']), reverse=True)
    if not candidates or number(candidates[0]['usage_percent']) <= 0:
        return {}
    if len(candidates) > 1 and number(candidates[0]['usage_percent']) == number(candidates[1]['usage_percent']):
        return {}
    return candidates[0]


def gpu_for_renderer(gpus, renderer):
    """Sólo enlaza un renderer a sensores con identidad exacta normalizada."""
    name = str(renderer or '').strip().casefold()
    matches = [g for g in gpus if isinstance(g, dict) and name
               and str(g.get('name') or '').strip().casefold() == name]
    return matches[0] if len(matches) == 1 else {}
