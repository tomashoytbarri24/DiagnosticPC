"""Adaptadores puros de evidencia existente; no consultan ni simulan sensores."""
import copy
import math
import re


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
    """Consolida dispositivo físico + uso real de volumen sin inventar datos.

    Los proveedores de sensores suelen conocer temperatura/vida del dispositivo
    físico, mientras psutil conoce el espacio usado del volumen montado. Antes
    ambas fuentes quedaban separadas y el diagnóstico podía mostrar ``N/A`` en
    Espacio aunque el sistema sí conociera el porcentaje.
    """
    devices = telemetry.get('_storage_devices') or []
    cache = telemetry.get('_storage_health_cache') or {}
    volumes = [copy.deepcopy(v) for v in (volumes or []) if isinstance(v, dict)]

    def norm(value):
        return re.sub(r'\s+', ' ', str(value or '').strip()).casefold()

    def matching_volume(device):
        dname = norm(device.get('model') or device.get('name'))
        exact = []
        fuzzy = []
        for volume in volumes:
            vname = norm(volume.get('model') or volume.get('name'))
            if dname and vname and dname == vname:
                exact.append(volume)
            elif dname and vname and (dname in vname or vname in dname):
                fuzzy.append(volume)
        if len(exact) == 1:
            return exact[0]
        if len(fuzzy) == 1:
            return fuzzy[0]
        if len(devices) == 1 and len(volumes) == 1:
            return volumes[0]
        return None

    output = []
    for index, device in enumerate(devices):
        if not isinstance(device, dict):
            continue
        row = copy.deepcopy(device)
        cached = cache.get(index, cache.get(str(index), {}))
        name = norm(device.get('model') or device.get('name'))
        cached_name = norm(cached.get('model'))
        if name and name == cached_name:
            row.update(copy.deepcopy(cached))
            health = number(cached.get('health'))
            if health is not None:
                row['health_percent'] = health
                row['life_percent'] = health

        volume = matching_volume(device)
        if volume:
            used = number(volume.get('used_percent', volume.get('used_space_percent')))
            total = number(volume.get('total_gb', volume.get('total_space_gb')))
            free = number(volume.get('free_gb', volume.get('free_space_gb')))
            health = number(volume.get('health', volume.get('health_percent')))
            if used is not None:
                row['used_percent'] = used
                row['used_space_percent'] = used
            if total is not None:
                row['total_space_gb'] = total
            if free is not None:
                row['free_space_gb'] = free
            if health is not None and 0 <= health <= 100 and physical_health(row) is None:
                row['health_percent'] = health
                row['life_percent'] = health
                row['health_source'] = volume.get('health_source')
        output.append(row)

    return output or volumes


def active_gpu(gpus):
    """Mayor actividad medida; un empate o uso cero no prueba qué GPU ejecuta la carga."""
    candidates = [g for g in gpus if isinstance(g, dict) and number(g.get('usage_percent')) is not None]
    candidates.sort(key=lambda g: number(g['usage_percent']), reverse=True)
    if not candidates or number(candidates[0]['usage_percent']) <= 0:
        return {}
    if len(candidates) > 1 and number(candidates[0]['usage_percent']) == number(candidates[1]['usage_percent']):
        return {}
    return candidates[0]


def normalize_gpu_identity(value):
    """Normaliza sólo sufijos de renderer conocidos; no adivina entre adaptadores."""
    text = re.sub(r"\s+", " ", str(value or "").strip()).casefold()
    # OpenGL en Windows puede añadir capacidades del bus/CPU al nombre exacto
    # del adaptador (p. ej. ``/PCIe/SSE2``). Se quitan únicamente sufijos
    # técnicos conocidos; el nombre base debe seguir coincidiendo de forma única.
    text = re.sub(r"/(?:pcie/)?sse(?:2|3|4(?:\.1|\.2)?)$", "", text)
    text = re.sub(r"/(?:pcie|sse(?:2|3|4(?:\.1|\.2)?))$", "", text)
    return text.strip()


def gpu_for_renderer(gpus, renderer):
    """Enlaza el renderer a una sola GPU tras normalización conservadora."""
    name = normalize_gpu_identity(renderer)
    matches = [g for g in gpus if isinstance(g, dict) and name
               and normalize_gpu_identity(g.get('name')) == name]
    return matches[0] if len(matches) == 1 else {}
