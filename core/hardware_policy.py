"""Políticas universales de identidad, selección y mapeo de hardware de CorePulse.

Este módulo no contiene excepciones por marca o modelo. Todas las decisiones usan
identidad y telemetría detectadas en tiempo de ejecución. Cuando una correspondencia
no puede demostrarse sin ambigüedad, se devuelve ``None``/``N/A`` en lugar de adivinar.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, Mapping, Optional


_GENERIC_TOKENS = {
    'device', 'hardware', 'unknown', 'generic', 'standard', 'system', 'default',
    'controller', 'adapter', 'display', 'graphics', 'video', 'processor', 'cpu', 'gpu',
    'storage', 'disk', 'drive', 'ssd', 'hdd', 'nvme', 'memory', 'ram', 'series', 'family',
    'integrated', 'basic', 'usb', 'scsi', 'sata', 'pcie', 'pci', 'm2', 'tm', 'r',
}


def clean_text(value: Any) -> str:
    """Normaliza texto sin inferir información ausente."""
    if value is None:
        return ''
    text = str(value).strip().strip('\x00')
    return re.sub(r'\s+', ' ', text)


def number(value: Any) -> Optional[float]:
    """Convierte un valor numérico real o devuelve ``None``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    try:
        value = float(str(value).strip())
        return value if math.isfinite(value) else None
    except Exception:
        return None


def normalize_hardware_label(value: Any) -> str:
    """Devuelve una representación comparable de una identidad de hardware."""
    text = clean_text(value).lower()
    text = re.sub(r'\(r\)|\(tm\)|[™®]', ' ', text)
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _identity_tokens(name: str) -> list[str]:
    return [token for token in normalize_hardware_label(name).split() if token]


def select_active_gpu(gpus: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Selecciona la GPU con mayor actividad real, sin asumir fabricante.

    El selector favorece uso de núcleo medido. Si no existe, utiliza la presencia de
    telemetría real como desempate. Si ningún adaptador expone métricas, conserva el
    primer adaptador detectado solo como elemento representativo de interfaz; esta
    selección no se interpreta como prueba de que sea la GPU principal del sistema.
    """
    candidates = [gpu for gpu in (gpus or []) if isinstance(gpu, dict)]
    if not candidates:
        return {}

    def score(item: tuple[int, Dict[str, Any]]) -> tuple[float, ...]:
        index, gpu = item
        usage = number(gpu.get('usage_percent'))
        memory_usage = number(gpu.get('memory_usage_percent'))
        temperature = number(gpu.get('temperature_c'))
        power = number(gpu.get('power_w'))
        valid_metrics = sum(v is not None for v in (usage, memory_usage, temperature, power))
        return (
            1.0 if usage is not None else 0.0,
            usage if usage is not None else -1.0,
            1.0 if power is not None else 0.0,
            power if power is not None else -1.0,
            1.0 if memory_usage is not None else 0.0,
            memory_usage if memory_usage is not None else -1.0,
            float(valid_metrics),
            -float(index),
        )

    return max(enumerate(candidates), key=score)[1]


def select_representative_gpu_stats(gpus: Mapping[str, Dict[str, Any]] | None) -> tuple[Optional[str], Dict[str, Any]]:
    """Selecciona estadísticas GPU para tendencias usando actividad medida.

    ``diagnostic_session`` almacena cada métrica como ``{avg,max,...}``. Esta función
    adapta ese formato a :func:`select_active_gpu` y devuelve también el nombre exacto
    de la entrada elegida. Nunca prioriza una marca concreta.
    """
    if not isinstance(gpus, Mapping) or not gpus:
        return None, {}
    adapted: list[Dict[str, Any]] = []
    names: list[str] = []
    for name, stats in gpus.items():
        if not isinstance(stats, dict):
            continue

        def avg(metric: str) -> Optional[float]:
            raw = stats.get(metric)
            if isinstance(raw, dict):
                return number(raw.get('avg'))
            return number(raw)

        adapted.append({
            '_name': str(name),
            '_stats': stats,
            'usage_percent': avg('usage_percent'),
            'memory_usage_percent': avg('memory_usage_percent'),
            'temperature_c': avg('temperature_c'),
            'power_w': avg('power_w'),
        })
        names.append(str(name))
    selected = select_active_gpu(adapted)
    if not selected:
        return None, {}
    return clean_text(selected.get('_name')) or None, selected.get('_stats') if isinstance(selected.get('_stats'), dict) else {}


def component_identity_specific(component_type: str, name: str, facts: Optional[Dict[str, Any]] = None) -> tuple[bool, str]:
    """Decide si una identidad es suficientemente específica para investigar vigencia.

    No usa marcas concretas. RAM se identifica por capacidad real; el resto requiere un
    nombre con señal de modelo suficiente (token alfanumérico o varios tokens distintivos).
    """
    ctype = clean_text(component_type).upper() or 'UNKNOWN'
    facts = facts if isinstance(facts, dict) else {}
    label = clean_text(name).split(' · ', 1)[0].strip()

    if ctype == 'RAM':
        total = number(facts.get('total_gb'))
        if total is not None and total > 0:
            return True, ''
        return False, 'RAM sin capacidad total real disponible.'

    if not label or label.upper() in {'N/A', 'UNKNOWN', 'DESCONOCIDO', 'NO DISPONIBLE'}:
        return False, 'La identidad del componente no está disponible.'

    tokens = _identity_tokens(label)
    meaningful = [token for token in tokens if token not in _GENERIC_TOKENS]
    has_model_token = any(any(ch.isdigit() for ch in token) for token in meaningful)
    sufficiently_named = len(meaningful) >= 3 and len(label) >= 10

    if has_model_token or sufficiently_named:
        return True, ''
    return False, f'La identidad reportada ({label}) no contiene un modelo suficientemente específico para una comparación verificable.'


def component_brand_tokens(component: Dict[str, Any]) -> tuple[str, ...]:
    """Obtiene tokens de fabricante de forma dinámica a partir del inventario real."""
    facts = component.get('facts') if isinstance(component.get('facts'), dict) else {}
    values: list[str] = []
    for key in ('manufacturer', 'vendor'):
        value = clean_text(facts.get(key))
        if value:
            values.append(value)
    raw_many = facts.get('manufacturers')
    if isinstance(raw_many, (list, tuple, set)):
        values.extend(clean_text(x) for x in raw_many if clean_text(x))

    # Una palabra del nombre comercial no demuestra propiedad de un dominio. Solo
    # datos explícitos de fabricante/vendor pueden elevar una fuente a "oficial".
    # Si Windows no entrega fabricante, la fuente puede seguir siendo útil como Tier
    # B/C, pero CorePulse no la promociona a Tier A por semejanza textual.
    tokens: list[str] = []
    for value in values:
        for token in _identity_tokens(value):
            if len(token) >= 3 and token not in _GENERIC_TOKENS and not token.isdigit():
                tokens.append(token)
    return tuple(dict.fromkeys(tokens[:8]))


def host_looks_official(host: str, component: Dict[str, Any]) -> bool:
    """Detecta una fuente probablemente oficial sin una tabla de fabricantes."""
    compact_host = re.sub(r'[^a-z0-9]+', '', clean_text(host).lower())
    if not compact_host:
        return False
    for token in component_brand_tokens(component):
        compact_token = re.sub(r'[^a-z0-9]+', '', token)
        if len(compact_token) >= 4 and compact_token in compact_host:
            return True
    return False


def device_support_target(device: Dict[str, Any]) -> str:
    """Construye el objetivo de soporte físico a partir del equipo detectado."""
    form = clean_text(device.get('form_factor')).upper()
    manufacturer = clean_text(device.get('manufacturer'))
    model = clean_text(device.get('model'))
    display_model = clean_text(device.get('display_model'))
    support_target = clean_text(device.get('support_target'))
    motherboard_raw = device.get('motherboard')
    if isinstance(motherboard_raw, dict):
        motherboard = ' '.join(
            item for item in (clean_text(motherboard_raw.get('manufacturer')), clean_text(motherboard_raw.get('model'))) if item
        ).strip()
    else:
        motherboard = clean_text(motherboard_raw)

    if support_target and support_target.upper() != 'N/A':
        return support_target
    if form == 'LAPTOP' and model and model.upper() != 'N/A':
        return ' '.join(x for x in (manufacturer, model) if x).strip()
    if form == 'DESKTOP':
        if model and model.upper() != 'N/A':
            return ' '.join(x for x in (manufacturer, model) if x).strip()
        if motherboard and motherboard.upper() != 'N/A':
            return motherboard
    return display_model or ' '.join(x for x in (manufacturer, model) if x and x.upper() != 'N/A').strip() or motherboard or 'N/A'


def resolve_component_id(component: Any, lookup: Mapping[str, Dict[str, Any]]) -> Optional[str]:
    """Resuelve una referencia de hallazgo a un componente del inventario sin adivinar.

    El mapeo acepta IDs exactos o coincidencias inequívocas de identidad. Si existen
    varios componentes del mismo tipo y la referencia no identifica cuál es, devuelve
    ``None``. Si solo existe uno del tipo solicitado, esa correspondencia es inequívoca.
    """
    if not isinstance(lookup, Mapping):
        return None
    raw_text = clean_text(component)
    if not raw_text:
        return None
    raw_upper = raw_text.upper()
    if raw_upper in lookup:
        return raw_upper
    for key in ('CPU', 'RAM', 'BATTERY'):
        if raw_upper == key and key in lookup:
            return key

    prefix = raw_upper.split(':', 1)[0]
    if prefix not in {'GPU', 'STORAGE'}:
        return None
    candidates = [(cid, info) for cid, info in lookup.items() if clean_text(info.get('type')).upper() == prefix]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0][0]

    needle = raw_text.split(':', 1)[1] if ':' in raw_text else raw_text
    needle_norm = normalize_hardware_label(needle)
    if not needle_norm:
        return None

    exact: list[str] = []
    partial: list[tuple[int, str]] = []
    needle_tokens = set(needle_norm.split())
    for cid, info in candidates:
        name = clean_text(info.get('name') or info.get('detected_hardware'))
        name = name.split(' · ', 1)[0]
        name_norm = normalize_hardware_label(name)
        if not name_norm:
            continue
        if needle_norm == name_norm:
            exact.append(cid)
            continue
        if needle_norm in name_norm or name_norm in needle_norm:
            partial.append((100, cid))
            continue
        tokens = set(name_norm.split())
        meaningful = (needle_tokens & tokens) - _GENERIC_TOKENS
        model_overlap = sum(1 for token in meaningful if any(ch.isdigit() for ch in token))
        score = len(meaningful) * 10 + model_overlap * 20
        if model_overlap >= 1 and len(meaningful) >= 2:
            partial.append((score, cid))

    if len(exact) == 1:
        return exact[0]
    if exact:
        return None
    if not partial:
        return None
    partial.sort(reverse=True)
    best_score = partial[0][0]
    winners = [cid for score, cid in partial if score == best_score]
    return winners[0] if len(winners) == 1 else None


__all__ = [
    'clean_text', 'number', 'normalize_hardware_label', 'select_active_gpu',
    'select_representative_gpu_stats', 'component_identity_specific',
    'component_brand_tokens', 'host_looks_official', 'device_support_target',
    'resolve_component_id',
]
