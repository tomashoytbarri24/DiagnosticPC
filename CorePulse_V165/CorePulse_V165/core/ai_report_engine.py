"""Coordina el análisis con IA del diagnóstico y prepara contenido explicativo para el reporte."""
# Código refactorizado: nombres estables y documentación en español.
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
import json
import math
import os
import re
import time
from core.device_identity import collect_hardware_inventory
from core.hardware_policy import resolve_component_id as resolve_inventory_component_id
from core.ai_evidence_research import research_device_support, research_hardware_relevance, _pace_provider, _error_status_code
from core.env_config import load_corepulse_env, ai_runtime_status
load_corepulse_env()
POLICY = 'AI_INTERPRETS_REAL_EVIDENCE_ONLY'
ALLOWED_RELEVANCE = {'OPTIMO', 'ESTANDAR', 'JUSTO', 'POR_DEBAJO_DEL_ESTANDAR', 'NO_EVALUABLE'}
ALLOWED_CONFIDENCE = {'ALTA', 'MEDIA', 'BAJA', 'NO_EVALUABLE'}
MODEL_PRIORITY = ('openai/gpt-oss-120b', 'qwen/qwen3.8-27b', 'openai/gpt-oss-20b', 'qwen/qwen3.6-27b')
STRICT_SCHEMA_MODELS = {'openai/gpt-oss-120b', 'openai/gpt-oss-20b', 'qwen/qwen3.8-27b'}
_URL_RE = re.compile('https?://\\S+|www\\.\\S+', re.I)
_CODE_FENCE_RE = re.compile('^```(?:json)?\\s*|\\s*```$', re.I | re.S)
_REPLACEMENT_ACTION_RE = re.compile(r'\b(reemplaz\w*|sustitu\w*|cambi\w*|actualiz\w*|upgrade\w*|ampli\w*|instal\w*)\b', re.I)

def _text(value: Any, default: str='') -> str:
    return default if value is None else str(value).strip()

def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []

def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    return None

def _strip_urls(value: Any) -> str:
    return _URL_RE.sub('[enlace omitido: no verificado]', _text(value)).strip()

def _sanitized_inventory(telemetry: Dict[str, Any], disks: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        inv = collect_hardware_inventory(telemetry=telemetry, disks=disks)
    except Exception:
        inv = {}
    identity = inv.get('identity') if isinstance(inv.get('identity'), dict) else {}
    board = identity.get('motherboard') if isinstance(identity.get('motherboard'), dict) else {}
    cpu = inv.get('cpu') if isinstance(inv.get('cpu'), dict) else {}
    ram = inv.get('ram') if isinstance(inv.get('ram'), dict) else {}
    gpus = _safe_list(inv.get('gpus'))
    storage = _safe_list(inv.get('storage'))
    battery = inv.get('battery') if isinstance(inv.get('battery'), dict) else None
    components: List[Dict[str, Any]] = []
    cpu_name = _text(cpu.get('name'))
    cpu_wmi = cpu.get('wmi') if isinstance(cpu.get('wmi'), dict) else {}
    if cpu_name:
        components.append({'id': 'CPU', 'type': 'CPU', 'name': cpu_name, 'facts': {'manufacturer': _text(cpu_wmi.get('manufacturer')) or None, 'cores': cpu_wmi.get('cores'), 'threads': cpu_wmi.get('threads'), 'max_clock_ghz': cpu_wmi.get('max_clock_ghz'), 'current_ghz': cpu.get('current_ghz')}})
    module_total = _num(ram.get('module_total_gb'))
    total = module_total if module_total is not None and module_total > 0 else ram.get('total_gb')
    modules = _safe_list(ram.get('modules'))
    ram_speeds = sorted({int(float(m.get('speed_mhz'))) for m in modules if isinstance(m, dict) and _num(m.get('speed_mhz'))})
    ram_manufacturers = sorted({_text(m.get('manufacturer')) for m in modules if isinstance(m, dict) and _text(m.get('manufacturer'))})
    ram_parts = sorted({_text(m.get('part_number')) for m in modules if isinstance(m, dict) and _text(m.get('part_number'))})
    components.append({'id': 'RAM', 'type': 'RAM', 'name': f'{float(total):.2f} GB RAM' if _num(total) and float(total) > 0 else 'RAM total no disponible', 'facts': {'total_gb': float(total) if _num(total) and float(total) > 0 else None, 'module_count': ram.get('module_count'), 'configured_speeds_mhz': ram_speeds, 'manufacturers': ram_manufacturers, 'part_numbers': ram_parts}})
    for idx, gpu in enumerate(gpus):
        if isinstance(gpu, dict):
            name = _text(gpu.get('name') or gpu.get('model'))
            if name:
                memory_total_mb = _num(gpu.get('memory_total_mb'))
                vram_wmi = _num(gpu.get('vram_gb_wmi'))
                vram_gb = round(memory_total_mb / 1024.0, 2) if memory_total_mb else round(vram_wmi, 2) if vram_wmi else None
                components.append({'id': f'GPU:{idx}', 'type': 'GPU', 'name': name, 'facts': {'vram_gb': vram_gb, 'manufacturer': _text(gpu.get('vendor')) or None, 'vendor': _text(gpu.get('vendor')) or None, 'video_processor': _text(gpu.get('video_processor')) or None}})
    for idx, disk in enumerate(storage):
        if not isinstance(disk, dict):
            continue
        name = _text(disk.get('model') or disk.get('name') or disk.get('device'), f'Unidad {idx + 1}')
        size = disk.get('size_gb') or disk.get('total_space_gb') or disk.get('total_gb') or disk.get('capacity_gb')
        suffix = f' · {float(size):.0f} GB' if _num(size) and float(size) > 0 else ''
        components.append({'id': f'STORAGE:{idx}', 'type': 'STORAGE', 'name': name + suffix, 'facts': {'capacity_gb': float(size) if _num(size) and float(size) > 0 else None, 'manufacturer': _text(disk.get('manufacturer') or disk.get('vendor')) or None, 'interface': _text(disk.get('interface') or disk.get('interface_type') or disk.get('bus_type')) or None, 'media_type': _text(disk.get('media_type') or disk.get('type')) or None}})
    if battery:
        components.append({'id': 'BATTERY', 'type': 'BATTERY', 'name': 'Batería del sistema', 'facts': {'present': True}})
    model = _text(identity.get('model'), 'N/A')
    display_model = _text(identity.get('display_model'), model)
    support_target = _text(identity.get('support_target'), display_model)
    board_name = ' '.join((x for x in (_text(board.get('manufacturer')), _text(board.get('model'))) if x)).strip() or 'N/A'
    return {'captured_at': time.time(), 'device': {'form_factor': _text(identity.get('form_factor'), 'UNKNOWN').upper(), 'manufacturer': _text(identity.get('manufacturer'), 'N/A'), 'model': model, 'display_model': display_model, 'support_target': support_target, 'motherboard': board_name}, 'components': components, 'policy': 'REAL_OS_IDENTITY_SANITIZED_NO_SERIALS'}

def _stats_digest(diagnostic: Dict[str, Any]) -> Dict[str, Any]:
    stats = diagnostic.get('statistics') if isinstance(diagnostic.get('statistics'), dict) else {}
    out: Dict[str, Any] = {'cpu': {}, 'ram': {}, 'gpus': {}, 'storage': {}, 'battery': None}
    cpu = stats.get('cpu') if isinstance(stats.get('cpu'), dict) else {}
    ram = stats.get('ram') if isinstance(stats.get('ram'), dict) else {}
    for key in ('usage_percent', 'package_temp_c', 'distance_to_tjmax_min_c', 'clock_avg_ghz'):
        if isinstance(cpu.get(key), dict):
            out['cpu'][key] = cpu[key]
    for key in ('seconds_within_5c_tjmax', 'seconds_within_10c_tjmax'):
        if key in cpu:
            out['cpu'][key] = cpu.get(key)
    if isinstance(ram.get('usage_percent'), dict):
        out['ram']['usage_percent'] = ram['usage_percent']
    for key in ('seconds_over_85_percent', 'seconds_over_90_percent', 'seconds_over_95_percent'):
        if key in ram:
            out['ram'][key] = ram.get(key)
    for name, gpu in (stats.get('gpus') or {}).items():
        if isinstance(gpu, dict):
            out['gpus'][str(name)] = {k: gpu.get(k) for k in ('usage_percent', 'temperature_c', 'hotspot_c', 'memory_usage_percent') if k in gpu}
    for name, drive in (stats.get('storage') or {}).items():
        if isinstance(drive, dict):
            out['storage'][str(name)] = {k: drive.get(k) for k in ('temperature_c', 'warning_temperature_c', 'critical_temperature_c', 'seconds_at_or_above_warning', 'seconds_at_or_above_critical', 'life_percent', 'used_space_percent') if k in drive}
    if isinstance(stats.get('battery'), dict):
        out['battery'] = {k: stats['battery'].get(k) for k in ('degradation_percent', 'designed_capacity_mwh', 'full_charge_capacity_mwh')}
    return out

def _diagnostic_digest(diagnostic: Dict[str, Any]) -> Dict[str, Any]:
    findings = []
    for item in _safe_list(diagnostic.get('findings')):
        if not isinstance(item, dict):
            continue
        findings.append({'component': _text(item.get('component'), 'GENERAL'), 'status': _text(item.get('status'), 'INFO').upper(), 'title': _text(item.get('title') or item.get('message'), 'Hallazgo'), 'explanation': _text(item.get('explanation')), 'evidence': [_text(x) for x in _safe_list(item.get('evidence')) if _text(x)], 'rule_source': _text(item.get('rule_source'))})
    adaptive = diagnostic.get('adaptive_diagnostic') if isinstance(diagnostic.get('adaptive_diagnostic'), dict) else {}
    return {'overall_status': _text(diagnostic.get('overall_status'), 'NO_EVALUABLE').upper(), 'session_valid': bool(diagnostic.get('session_valid')), 'context': _text(adaptive.get('context'), 'N/A'), 'findings': findings, 'statistics': _stats_digest(diagnostic), 'policy': 'CURRENT_DIAGNOSTIC_ONLY_NUMERIC_EVIDENCE_ALLOWED'}

def _component_lookup(inventory: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    out = {}
    for item in _safe_list(inventory.get('components')):
        if isinstance(item, dict) and _text(item.get('id')):
            cid = _text(item.get('id'))
            out[cid] = {'id': cid, 'type': _text(item.get('type'), 'UNKNOWN'), 'name': _text(item.get('name'), 'N/A')}
    return out

def _resolve_component_id(component: str, lookup: Dict[str, Dict[str, str]]) -> str:
    """Resuelve hallazgos contra el inventario sin seleccionar dispositivos arbitrarios."""
    resolved = resolve_inventory_component_id(component, lookup)
    if resolved:
        return resolved
    raw = _text(component).upper()
    # Una referencia no resuelta se conserva como evidencia del hallazgo, pero no se
    # reasigna a la primera GPU/unidad disponible. Así evitamos atribuciones falsas en
    # equipos multi-GPU o con múltiples unidades.
    return raw or 'UNRESOLVED'

def _problem_cases(diagnostic: Dict[str, Any], inventory: Dict[str, Any]) -> List[Dict[str, Any]]:
    lookup = _component_lookup(inventory)
    problems = []
    seen = set()
    for idx, item in enumerate(_safe_list(diagnostic.get('findings'))):
        if not isinstance(item, dict):
            continue
        status = _text(item.get('status'), 'INFO').upper()
        if status not in {'WARNING', 'CRITICAL'}:
            continue
        cid = _resolve_component_id(_text(item.get('component')), lookup)
        ctype = (lookup.get(cid) or {}).get('type') or cid.split(':', 1)[0]
        pid = f'FINDING:{idx}:{cid}'
        title = _text(item.get('title'), 'Condición detectada')
        component_name = (lookup.get(cid) or {}).get('name') or 'N/A'
        title_low = title.lower()
        if ctype == 'CPU' and any(x in title_low for x in ('tjmax', 'temperatura', 'térm', 'term')):
            tutorial_action = 'limpieza de ventiladores, disipador, pasta térmica y desmontaje seguro'
        elif ctype == 'GPU' and any(x in title_low for x in ('hotspot', 'temperatura', 'térm', 'term')):
            tutorial_action = 'limpieza de refrigeración GPU, ventiladores, disipador y thermal pads'
        elif ctype == 'RAM':
            tutorial_action = 'acceso a RAM, slots, ampliación compatible y desmontaje del modelo exacto'
        elif ctype == 'STORAGE' and any(x in title_low for x in ('espacio', 'ocupaci', 'margen')):
            tutorial_action = 'acceso a SSD M.2, ampliación de almacenamiento e instalación compatible'
        elif ctype == 'STORAGE':
            tutorial_action = 'acceso, diagnóstico, refrigeración o reemplazo de SSD del modelo exacto'
        elif ctype == 'BATTERY':
            tutorial_action = 'acceso y reemplazo seguro de batería del modelo exacto'
        else:
            tutorial_action = 'mantenimiento y solución de la condición detectada'
        problems.append({'problem_id': pid, 'component_id': cid, 'component_type': ctype, 'component_name': component_name, 'severity': status, 'title': title, 'explanation': _text(item.get('explanation')), 'evidence': [_text(x) for x in _safe_list(item.get('evidence')) if _text(x)], 'rule_source': _text(item.get('rule_source')), 'tutorial_action': tutorial_action})
        seen.add((cid, title_low))
    stats = diagnostic.get('statistics') if isinstance(diagnostic.get('statistics'), dict) else {}
    for name, drive in (stats.get('storage') or {}).items():
        if not isinstance(drive, dict):
            continue
        used = _num(drive.get('used_space_percent'))
        if used is not None and used >= 90.0:
            fake = f'STORAGE:{name}'
            cid = _resolve_component_id(fake, lookup)
            has_capacity_finding = any((p.get('component_id') == cid and any(x in _text(p.get('title')).lower() for x in ('espacio', 'ocupaci', 'margen'))) for p in problems)
            pid = f'CAPACITY:{cid}'
            if not has_capacity_finding:
                problems.append({'problem_id': pid, 'component_id': cid, 'component_type': 'STORAGE', 'component_name': (lookup.get(cid) or {}).get('name') or _text(name, 'N/A'), 'severity': 'WARNING_ADVISORY', 'title': 'Poco espacio libre en almacenamiento', 'explanation': 'La unidad alcanzó 90% o más de ocupación. Esta es una política de capacidad de CorePulse, no un fallo SMART.', 'evidence': [f'Espacio usado medido: {used:.1f}%'], 'rule_source': 'CorePulse capacity policy >=90% used', 'tutorial_action': 'acceso a SSD M.2, ampliación de almacenamiento e instalación compatible', 'metric_value': used})
    for name, gpu in (stats.get('gpus') or {}).items():
        if not isinstance(gpu, dict):
            continue
        hs = gpu.get('hotspot_c') if isinstance(gpu.get('hotspot_c'), dict) else {}
        hmax = _num(hs.get('max'))
        samples = int(hs.get('samples') or 0)
        if hmax is not None and samples > 0 and (hmax >= 100.0):
            cid = _resolve_component_id(f'GPU:{name}', lookup)
            pid = f'GPUHOTSPOT:{cid}'
            problems.append({'problem_id': pid, 'component_id': cid, 'component_type': 'GPU', 'component_name': (lookup.get(cid) or {}).get('name') or _text(name, 'N/A'), 'severity': 'WARNING_ADVISORY', 'title': 'Pico de hotspot GPU elevado', 'explanation': 'CorePulse observó un hotspot de 100 °C o más. Es una heurística conservadora de atención, no un límite oficial específico del fabricante.', 'evidence': [f'Hotspot máximo observado: {hmax:.1f} °C', f'Muestras válidas de hotspot: {samples}'], 'rule_source': 'CorePulse GPU hotspot advisory >=100C', 'tutorial_action': 'limpieza del sistema de refrigeración y mantenimiento térmico de GPU', 'metric_value': hmax})
    return [_decorate_problem_priority(p) for p in problems]

def _decorate_problem_priority(problem: Dict[str, Any]) -> Dict[str, Any]:
    """Gestiona la operación `decorate_problem_priority` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    p = dict(problem)
    sev = _text(p.get('severity'), 'INFO').upper()
    title = _text(p.get('title')).lower()
    metric = _num(p.get('metric_value'))
    if sev == 'CRITICAL':
        level = 'URGENTE'
        reason = 'CorePulse clasificó esta condición como CRITICAL a partir de evidencia real.'
    elif sev == 'WARNING':
        level = 'PRIORITARIO'
        reason = 'CorePulse confirmó una condición WARNING sostenida que requiere corrección o seguimiento.'
    elif sev == 'WARNING_ADVISORY' and 'poco espacio' in title and (metric is not None) and (metric >= 95.0):
        level = 'PRIORITARIO'
        reason = 'La unidad tiene 95% o más de ocupación según la política de capacidad de CorePulse.'
    elif sev == 'WARNING_ADVISORY' and 'hotspot' in title:
        level = 'PRIORITARIO'
        reason = 'CorePulse activó su advisory térmico de hotspot GPU; no se interpreta como límite oficial del fabricante.'
    else:
        level = 'RECOMENDADO'
        reason = 'Condición real que merece una recomendación, sin prioridad crítica.'
    p['priority_level'] = level
    p['priority_required'] = level in {'URGENTE', 'PRIORITARIO'}
    p['priority_reason'] = reason
    return p

def _default_risk(problem: Dict[str, Any]) -> str:
    sev = _text(problem.get('severity'), 'INFO').upper()
    ctype = _text(problem.get('component_type'), 'GENERAL').upper()
    title = _text(problem.get('title')).lower()
    if sev == 'CRITICAL':
        return 'La condición fue clasificada CRITICAL por CorePulse. Mantenerla puede afectar estabilidad, rendimiento o vida útil; conviene corregirla antes de cargas exigentes.'
    if ctype in {'CPU', 'GPU', 'STORAGE'} and any((x in title for x in ('temperatura', 'tjmax', 'hotspot', 'térm', 'term'))):
        return 'Una condición térmica sostenida puede provocar reducción de rendimiento, throttling o estrés térmico. CorePulse recomienda corregir la causa y volver a medir.'
    if ctype == 'RAM':
        return 'La presión sostenida de memoria puede causar paginación, cierres, stutter y pérdida de respuesta, aunque no implica por sí sola un fallo físico de la RAM.'
    if ctype == 'STORAGE' and 'espacio' in title:
        return 'Un espacio libre muy reducido puede dificultar actualizaciones, archivos temporales y paginación, y degradar la experiencia general del sistema.'
    return 'La condición puede afectar la estabilidad o el rendimiento si persiste. Debe verificarse después de aplicar la corrección recomendada.'

def _default_actions(problem: Dict[str, Any], *, form: str, upgrade_status: str) -> List[str]:
    ctype = _text(problem.get('component_type'), 'GENERAL').upper()
    title = _text(problem.get('title')).lower()
    if ctype == 'CPU':
        return ['Comprobar que entradas y salidas de aire no estén obstruidas.', 'Limpiar ventiladores y disipador siguiendo el procedimiento del modelo exacto.', 'Revisar pasta térmica y contacto del disipador solo si el mantenimiento físico corresponde y puede hacerse de forma segura.', 'Repetir el diagnóstico CorePulse y comparar temperatura, distancia a TjMax y duración de la condición.']
    if ctype == 'GPU':
        return ['Comprobar ventilación y limpiar el sistema de refrigeración del equipo.', 'Revisar ventiladores, disipador y mantenimiento térmico siguiendo el procedimiento del modelo exacto.', 'No sustituir ni ampliar la GPU sin verificar primero que el equipo exacto admita físicamente esa intervención.', 'Repetir el diagnóstico y comparar temperatura/hotspot con la nueva sesión.']
    if ctype == 'RAM':
        base = ['Identificar procesos con mayor consumo de memoria y cerrar únicamente los que no sean necesarios.', 'Revisar programas de inicio y cargas residentes que mantengan presión sostenida de RAM.', 'Repetir el diagnóstico para confirmar que la presión de memoria disminuyó.']
        if upgrade_status == 'VERIFIED_UPGRADEABLE':
            base.append('Si el uso real lo justifica, evaluar una ampliación de RAM compatible con el modelo exacto.')
        else:
            base.append('No comprar RAM hasta verificar físicamente slots, memoria soldada y capacidad máxima del modelo exacto.')
        return base
    if ctype == 'STORAGE' and 'espacio' in title:
        base = ['Liberar temporales y contenido innecesario con herramientas seguras y revisar archivos de gran tamaño.', 'Mantener margen libre suficiente para actualizaciones, temporales y paginación.', 'Respaldar datos importantes antes de cualquier reemplazo o migración de unidad.']
        if upgrade_status == 'VERIFIED_UPGRADEABLE':
            base.append('Si la capacidad sigue siendo insuficiente, evaluar ampliación/reemplazo por una unidad compatible verificada.')
        else:
            base.append('No comprar una unidad nueva hasta verificar interfaz, formato físico, slots y compatibilidad del modelo exacto.')
        return base
    if ctype == 'STORAGE':
        return ['Respaldar datos importantes antes de intervenir la unidad.', 'Comprobar ventilación y montaje de la unidad si existe una condición térmica.', 'Si CorePulse o SMART reportan degradación real, priorizar respaldo y evaluar reemplazo compatible.', 'Repetir el diagnóstico después de la corrección y comparar temperatura/estado reportado.']
    return ['Aplicar una corrección segura basada en la evidencia y repetir el diagnóstico para confirmar el resultado.']

def _default_supplies(problem: Dict[str, Any], *, form: str, upgrade_status: str) -> List[str]:
    ctype = _text(problem.get('component_type'), 'GENERAL').upper()
    title = _text(problem.get('title')).lower()
    if ctype in {'CPU', 'GPU'}:
        return ['Destornilladores adecuados al modelo', 'Aire comprimido o soplador seguro para electrónica', 'Herramientas plásticas de apertura', 'Alcohol isopropílico y paño sin pelusa si se realiza limpieza térmica', 'Pasta térmica compatible solo si el procedimiento requiere repaste']
    if ctype == 'RAM':
        if upgrade_status == 'VERIFIED_UPGRADEABLE':
            return ['Módulo RAM compatible verificado', 'Destornilladores adecuados', 'Herramienta plástica de apertura', 'Protección ESD recomendada']
        return ['Administrador de tareas/CorePulse para identificar consumo', 'No comprar módulos hasta verificar compatibilidad física']
    if ctype == 'STORAGE' and 'espacio' in title:
        items = ['Unidad externa o destino de respaldo para datos importantes']
        if upgrade_status == 'VERIFIED_UPGRADEABLE':
            items += ['SSD/unidad compatible verificada', 'Destornilladores adecuados', 'Herramienta plástica de apertura']
        else:
            items += ['No comprar SSD/unidad hasta verificar formato, interfaz y slots disponibles']
        return items
    if ctype == 'STORAGE':
        return ['Unidad externa para respaldo', 'Destornilladores adecuados al equipo', 'Protección ESD recomendada']
    return ['No se requieren insumos físicos específicos para la primera etapa de verificación.']

def _default_precautions(problem: Dict[str, Any], *, form: str) -> List[str]:
    ctype = _text(problem.get('component_type'), 'GENERAL').upper()
    if ctype in {'CPU', 'GPU', 'RAM', 'STORAGE'}:
        out = ['Apagar completamente el equipo y desconectar alimentación antes de abrirlo.', 'Evitar electricidad estática y no forzar conectores, clips ni tornillos.']
        if form == 'LAPTOP':
            out.append('Desconectar la batería interna cuando el procedimiento del fabricante lo permita antes de manipular componentes.')
        if ctype == 'STORAGE':
            out.append('Realizar respaldo de datos importantes antes de reemplazar o migrar una unidad.')
        out.append('Si el equipo está en garantía o el procedimiento no es seguro para el usuario, acudir a servicio técnico.')
        return out
    return ['No realizar cambios destructivos sin respaldo y sin verificar el procedimiento correspondiente.']

def _schema(component_ids: Optional[List[str]]=None) -> Dict[str, Any]:
    ids = [str(x) for x in component_ids or [] if _text(x)]
    component_id_schema = {'type': 'string'}
    if ids:
        component_id_schema['enum'] = ids
    relevance = {'type': 'object', 'properties': {'component_id': component_id_schema, 'classification': {'type': 'string', 'enum': sorted(ALLOWED_RELEVANCE)}, 'confidence': {'type': 'string', 'enum': sorted(ALLOWED_CONFIDENCE)}, 'reason': {'type': 'string'}}, 'required': ['component_id', 'classification', 'confidence', 'reason'], 'additionalProperties': False}
    plan = {'type': 'object', 'properties': {'problem_id': {'type': 'string'}, 'component_id': {'type': 'string'}, 'summary': {'type': 'string'}, 'risk': {'type': 'string'}, 'possible_causes': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 5}, 'actions': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 7}, 'supplies': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 7}, 'precautions': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 6}, 'upgrade_note': {'type': 'string'}}, 'required': ['problem_id', 'component_id', 'summary', 'risk', 'possible_causes', 'actions', 'supplies', 'precautions', 'upgrade_note'], 'additionalProperties': False}
    return {'type': 'object', 'properties': {'executive_summary': {'type': 'string'}, 'hardware_relevance': {'type': 'array', 'items': relevance, 'minItems': len(ids), 'maxItems': len(ids)} if ids else {'type': 'array', 'items': relevance}, 'problem_recommendations': {'type': 'array', 'items': plan}, 'recommendations': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 6}, 'limitations': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 6}}, 'required': ['executive_summary', 'hardware_relevance', 'problem_recommendations', 'recommendations', 'limitations'], 'additionalProperties': False}

def _fallback_result(inventory: Dict[str, Any], reason: str, *, year: int, model=None, available=None) -> Dict[str, Any]:
    rows = []
    for comp in _component_lookup(inventory).values():
        rows.append({'component_id': comp['id'], 'component_type': comp['type'], 'detected_hardware': comp['name'], 'classification': 'NO_EVALUABLE', 'confidence': 'BAJA', 'reason': f'No fue posible verificar la vigencia actual de este componente: {reason}'})
    return {'version': VERSION, 'status': 'UNAVAILABLE', 'provider': 'GROQ', 'model': model, 'available_models': list(available or []), 'current_year': year, 'executive_summary': 'El PDF técnico se generó correctamente, pero el análisis de IA no estuvo disponible.', 'hardware_relevance': rows, 'problem_recommendations': [], 'recommendations': [], 'limitations': [reason], 'research': {'status': 'UNAVAILABLE', 'capability': 'UNAVAILABLE', 'model': None, 'tutorials': {}, 'upgradeability': {}, 'sources': [], 'source_count': 0, 'search_executed': False, 'visit_executed': False, 'executed_tools_count': 0, 'tool_types': [], 'reason': reason}, 'policy': {'evidence_only': True, 'no_sensor_fabrication': True, 'no_unverified_urls': True, 'technical_pdf_survives_ai_failure': True, 'pdf_domains_separate': True, 'unverified_component_replacement_blocked': True, 'priority_action_plan_for_harmful_parameters': True}}

def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    raw = _text(text)
    if not raw:
        return None
    raw = _CODE_FENCE_RE.sub('', raw).strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    a, b = (raw.find('{'), raw.rfind('}'))
    if a >= 0 and b > a:
        try:
            obj = json.loads(raw[a:b + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None

def _available_models(client) -> List[str]:
    try:
        data = client.models.list().data
        return sorted({_text(getattr(x, 'id', None) if not isinstance(x, dict) else x.get('id')) for x in data if _text(getattr(x, 'id', None) if not isinstance(x, dict) else x.get('id'))})
    except Exception:
        return []

def _select_model(available: Iterable[str], requested: Optional[str]=None) -> Optional[str]:
    aset = set((str(x) for x in available))
    req = _text(requested)
    if req and req in aset:
        return req
    return next((m for m in MODEL_PRIORITY if m in aset), None)

def _call_analysis(client, model: str, inventory: Dict[str, Any], diagnostic: Dict[str, Any], problems: List[Dict[str, Any]], year: int, *, response_mode: str='strict'):
    ids = [x.get('id') for x in _safe_list(inventory.get('components')) if isinstance(x, dict)]
    pids = [x.get('problem_id') for x in problems]
    form = _text((inventory.get('device') or {}).get('form_factor'), 'UNKNOWN').upper()
    prompt = f'\nEres la capa explicativa de CorePulse para un PDF técnico. Año: {year}.\n\nREGLAS NO NEGOCIABLES:\n- Usa SOLO inventario, hallazgos y estadísticas reales entregados.\n- NO inventes métricas, modelos, SMART, FPS, fallos ni causas confirmadas.\n- Los problem_id={pids} ya fueron determinados por reglas CorePulse. No agregues problemas nuevos.\n- Debes responder sobre TODOS los problem_id autorizados. Si no puedes aportar una causa concreta, usa una causa posible prudente, pero nunca omitas el problema.\n- Las causas deben expresarse como POSIBLES cuando no están confirmadas.\n- Para cada problema entrega: riesgo, posibles causas, pasos concretos, insumos/herramientas y precauciones.\n- Si priority_required=true, esos campos son OBLIGATORIOS y específicos al componente. Si la primera etapa no requiere insumos físicos, indícalo explícitamente.\n- El tutorial exacto NO lo inventas tú: otra capa lo busca y verifica para el modelo exacto.\n- No escribas URLs ni nombres de videos.\n- Salud técnica y vigencia {year} son distintas.\n- DOMINIO A - VIGENCIA: hardware_relevance es OBLIGATORIO e INDEPENDIENTE del plan de acción. Debe evaluar TODOS los component_id={ids}, aunque no exista ningún problema técnico.\n- La clasificación final de vigencia será validada por una capa web separada; no omitas filas aunque no conozcas un modelo. Si falta base suficiente, usa NO_EVALUABLE con confianza BAJA y explica exactamente qué evidencia falta.\n- Confianza ALTA requiere identidad/especificaciones suficientemente claras; MEDIA implica evidencia parcial pero útil; BAJA implica limitación importante. Nunca dejes confianza ni razón vacías.\n- DOMINIO B - PLAN DE ACCIÓN: problem_recommendations solo puede contener los problem_id={pids} autorizados por CorePulse. No reemplaza ni resume hardware_relevance.\n- Nunca uses una recomendación como sustituto de la clasificación anual, ni una clasificación anual como si fuera un problema técnico.\n- Clasifica cada component_id={ids} como OPTIMO/ESTANDAR/JUSTO/POR_DEBAJO_DEL_ESTANDAR/NO_EVALUABLE.\n- Equipo form_factor={form}.\n- No asumas reemplazabilidad, soldadura, slots ni compatibilidad por marca, modelo o factor de forma.\n- CPU/GPU/RAM/STORAGE: cualquier recomendación de sustitución, ampliación o instalación física debe quedar condicionada a la verificación web de la plataforma exacta.\n- Si la reemplazabilidad/compatibilidad no está verificada, limita el plan a diagnóstico, mantenimiento seguro y verificación previa; no recomiendes una compra concreta como compatible.\n- Mantén el texto profesional, accionable y conciso para una tabla PDF.\n\nINVENTARIO REAL:\n{json.dumps(inventory, ensure_ascii=False, indent=2)}\n\nDIAGNÓSTICO Y ESTADÍSTICAS REALES:\n{json.dumps(diagnostic, ensure_ascii=False, indent=2)}\n\nPROBLEMAS AUTORIZADOS PARA RECOMENDACIONES (priority_level/priority_required fueron calculados por CorePulse y NO por la IA):\n{json.dumps(problems, ensure_ascii=False, indent=2)}\n'.strip()
    kwargs = {'model': model, 'temperature': 0.1, 'max_completion_tokens': 3400, 'messages': [{'role': 'system', 'content': 'CorePulse: evidencia real primero. Responde JSON estricto y no inventes hechos.'}, {'role': 'user', 'content': prompt}]}
    if model.startswith('openai/gpt-oss'):
        kwargs.update({'include_reasoning': False, 'reasoning_effort': 'low'})
    elif model.startswith('qwen/qwen3.8'):
        kwargs.update({'reasoning_effort': 'none'})
    if response_mode == 'strict' and model in STRICT_SCHEMA_MODELS:
        kwargs['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'corepulse_ai_report', 'strict': True, 'schema': _schema(ids)}}
    else:
        kwargs['response_format'] = {'type': 'json_object'}
    return client.chat.completions.create(**kwargs)

def _sanitize_plan_actions(actions: List[str], *, form: str, ctype: str, upgrade_status: str) -> List[str]:
    """Bloquea recomendaciones físicas no verificadas para cualquier plataforma.

    ``form`` se conserva por compatibilidad de firma, pero no se usa para asumir que un
    componente está soldado o es reemplazable. La autoridad es ``upgrade_status``.
    """
    out = []
    ctype = _text(ctype, 'GENERAL').upper()
    verified = _text(upgrade_status).upper() == 'VERIFIED_UPGRADEABLE'
    for raw in actions[:7]:
        txt = _strip_urls(raw)
        if not txt:
            continue
        if ctype in {'CPU', 'GPU', 'RAM', 'STORAGE'} and (not verified) and _REPLACEMENT_ACTION_RE.search(txt):
            txt = (
                'Verificar primero la reemplazabilidad, interfaz/slots y compatibilidad física del '
                'componente en la plataforma exacta antes de considerar una sustitución, ampliación o instalación.'
            )
        if txt not in out:
            out.append(txt)
    return out

def _normalize(payload: Dict[str, Any], inventory: Dict[str, Any], diagnostic: Dict[str, Any], problems: List[Dict[str, Any]], research: Dict[str, Any], *, year: int, model: str, available: List[str]) -> Dict[str, Any]:
    lookup = _component_lookup(inventory)
    problem_map = {p['problem_id']: p for p in problems}
    relevance = {}
    research_rows = _safe_list(research.get('hardware_relevance'))
    for item in research_rows:
        if not isinstance(item, dict):
            continue
        cid = _text(item.get('component_id'))
        if cid not in lookup:
            continue
        cl = _text(item.get('classification'), 'NO_EVALUABLE').upper()
        cf = _text(item.get('confidence'), 'BAJA').upper()
        if cl not in ALLOWED_RELEVANCE:
            cl = 'NO_EVALUABLE'
        if cf not in {'ALTA', 'MEDIA', 'BAJA'}:
            cf = 'BAJA'
        reason = _strip_urls(item.get('reason')) or 'No fue posible justificar la vigencia con evidencia web suficiente.'
        relevance[cid] = {'component_id': cid, 'component_type': lookup[cid]['type'], 'detected_hardware': lookup[cid]['name'], 'classification': cl, 'confidence': cf, 'reason': reason, 'source_count': int(item.get('source_count') or 0)}
    relevance_reason = _text(research.get('relevance_reason') or research.get('reason'), 'No hubo evidencia web verificable suficiente para evaluar este componente.')
    rows = []
    for cid, c in lookup.items():
        rows.append(relevance.get(cid) or {'component_id': cid, 'component_type': c['type'], 'detected_hardware': c['name'], 'classification': 'NO_EVALUABLE', 'confidence': 'BAJA', 'reason': relevance_reason, 'source_count': 0})
    upgrades = research.get('upgradeability') if isinstance(research.get('upgradeability'), dict) else {}
    upgrades_by_component = research.get('upgradeability_by_component') if isinstance(research.get('upgradeability_by_component'), dict) else {}
    tutorials = research.get('tutorials') if isinstance(research.get('tutorials'), dict) else {}
    form = _text((inventory.get('device') or {}).get('form_factor'), 'UNKNOWN').upper()
    plans = []
    incoming = {_text(x.get('problem_id')): x for x in _safe_list(payload.get('problem_recommendations')) if isinstance(x, dict)}
    for pid, p in problem_map.items():
        item = incoming.get(pid) or {}
        ctype = _text(p.get('component_type'), 'GENERAL').upper()
        component_key = _text(p.get('component_id'))
        up = upgrades_by_component.get(component_key) if isinstance(upgrades_by_component.get(component_key), dict) else upgrades.get(ctype) if isinstance(upgrades.get(ctype), dict) else {'status': 'UNVERIFIED', 'reason': 'Actualización física no verificada.', 'source_url': None}
        actions = _sanitize_plan_actions(_safe_list(item.get('actions')), form=form, ctype=ctype, upgrade_status=_text(up.get('status')))
        if not actions:
            actions = _default_actions(p, form=form, upgrade_status=_text(up.get('status')))
        supplies = [_strip_urls(x) for x in _safe_list(item.get('supplies'))[:7] if _strip_urls(x)]
        if not supplies:
            supplies = _default_supplies(p, form=form, upgrade_status=_text(up.get('status')))
        precautions = [_strip_urls(x) for x in _safe_list(item.get('precautions'))[:6] if _strip_urls(x)]
        if not precautions:
            precautions = _default_precautions(p, form=form)
        risk = _strip_urls(item.get('risk')) or _default_risk(p)
        tut = tutorials.get(pid) if isinstance(tutorials.get(pid), dict) else {'status': 'NOT_FOUND', 'reason': 'No se encontró un tutorial exacto y verificable para este modelo.'}
        plans.append({'problem_id': pid, 'component_id': p.get('component_id'), 'component_type': ctype, 'severity': p.get('severity'), 'title': p.get('title'), 'priority_level': p.get('priority_level') or 'RECOMENDADO', 'priority_required': bool(p.get('priority_required')), 'priority_reason': p.get('priority_reason'), 'evidence': p.get('evidence') or [], 'rule_source': p.get('rule_source'), 'summary': _strip_urls(item.get('summary')) or p.get('explanation') or 'Condición detectada por CorePulse.', 'risk': risk, 'possible_causes': [_strip_urls(x) for x in _safe_list(item.get('possible_causes'))[:5] if _strip_urls(x)], 'actions': actions, 'supplies': supplies, 'precautions': precautions, 'upgrade_guidance': up, 'tutorial': tut})
    recs = [_strip_urls(x) for x in _safe_list(payload.get('recommendations'))[:6] if _strip_urls(x)]
    limits = [_strip_urls(x) for x in _safe_list(payload.get('limitations'))[:6] if _strip_urls(x)]
    return {'version': VERSION, 'status': 'OK', 'provider': 'GROQ', 'model': model, 'available_models': available, 'current_year': year, 'executive_summary': _strip_urls(payload.get('executive_summary')) or 'Análisis IA completado.', 'hardware_relevance': rows, 'problem_recommendations': plans, 'recommendations': recs, 'limitations': limits, 'research': research, 'policy': {'evidence_only': True, 'no_sensor_fabrication': True, 'no_unverified_urls': True, 'technical_pdf_survives_ai_failure': True, 'relevance_year_dynamic': True, 'pdf_domains_separate': True, 'unverified_component_replacement_blocked': True, 'tutorial_requires_web_and_oembed_verification': True, 'priority_action_plan_for_harmful_parameters': True, 'priority_plan_requires_supplies_precautions_and_tutorial_result': True}}

def _candidate_models(available: Iterable[str], requested: Optional[str]=None) -> List[str]:
    """Gestiona la operación `candidate_models` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    aset = {str(x) for x in available if _text(x)}
    out: List[str] = []
    req = _text(requested)
    if req and (not aset or req in aset):
        out.append(req)
    for mid in MODEL_PRIORITY:
        if (not aset or mid in aset) and mid not in out:
            out.append(mid)
    return out

def analyze_report_with_ai(diagnostic_result: Dict[str, Any], telemetry: Dict[str, Any], disks: List[Dict[str, Any]], *, api_key: Optional[str]=None, model: Optional[str]=None) -> Dict[str, Any]:
    env_state = load_corepulse_env()
    runtime_state = ai_runtime_status()
    year = datetime.now().year
    print(f"[CorePulse AI] config={runtime_state.get('status')} | web={runtime_state.get('web_research_enabled')} | model={runtime_state.get('requested_model')}")
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    disks = disks if isinstance(disks, list) else []
    diagnostic_result = diagnostic_result if isinstance(diagnostic_result, dict) else {}
    inventory = _sanitized_inventory(telemetry, disks)
    diagnostic = _diagnostic_digest(diagnostic_result)
    problems = _problem_cases(diagnostic, inventory)
    enabled = _text(os.getenv('COREPULSE_AI_ENABLED', '1')).lower() not in {'0', 'false', 'off', 'no'}
    if not enabled:
        r = _fallback_result(inventory, 'COREPULSE_AI_ENABLED desactivado.', year=year)
        r.update({'inventory': inventory, 'diagnostic': diagnostic, 'detected_problems': problems, 'env': {'loaded': bool(env_state.get('loaded')), 'loader': env_state.get('loader'), 'ai_runtime': runtime_state}})
        return r
    key = _text(api_key or os.getenv('GROQ_API_KEY'))
    if not key:
        reason = 'GROQ_API_KEY no configurada. CorePulse revisó variables de Windows/PowerShell y el .env local.'
        r = _fallback_result(inventory, reason, year=year)
        r.update({'inventory': inventory, 'diagnostic': diagnostic, 'detected_problems': problems, 'env': {'loaded': bool(env_state.get('loaded')), 'path': env_state.get('path'), 'loader': env_state.get('loader'), 'ai_runtime': runtime_state}})
        return r
    try:
        from groq import Groq
        client = Groq(api_key=key, timeout=45.0)
    except Exception as exc:
        r = _fallback_result(inventory, f'Groq SDK no disponible: {type(exc).__name__}: {exc}', year=year)
        r.update({'inventory': inventory, 'diagnostic': diagnostic, 'detected_problems': problems, 'env': {'loaded': bool(env_state.get('loaded')), 'loader': env_state.get('loader'), 'ai_runtime': runtime_state}})
        return r
    available = _available_models(client)
    print(f"[CorePulse AI] provider=CONNECTED | models_discovered={len(available)}")
    requested = _text(model or os.getenv('COREPULSE_GROQ_MODEL'))
    candidates = _candidate_models(available, requested)
    if not candidates:
        r = _fallback_result(inventory, 'No hay un modelo de análisis compatible disponible para esta cuenta de Groq.', year=year, available=available)
        r.update({'inventory': inventory, 'diagnostic': diagnostic, 'detected_problems': problems, 'env': {'loaded': bool(env_state.get('loaded')), 'loader': env_state.get('loader'), 'ai_runtime': runtime_state}})
        return r
    relevance_research = research_hardware_relevance(api_key=key, available_models=available, components=_safe_list(inventory.get('components')), year=year)
    if problems:
        support_research = research_device_support(api_key=key, available_models=available, device=inventory.get('device') or {}, problems=problems)
    else:
        support_research = {'status': 'NOT_REQUIRED', 'capability': 'AVAILABLE', 'model': None, 'tutorials': {}, 'upgradeability': {}, 'sources': [], 'source_count': 0, 'search_executed': False, 'visit_executed': False, 'executed_tools_count': 0, 'tool_types': [], 'reason': 'Sin problemas técnicos confirmados: no se consumió cuota web en tutoriales/actualizabilidad.'}
    research = dict(support_research if isinstance(support_research, dict) else {})
    research['hardware_relevance'] = _safe_list((relevance_research or {}).get('hardware_relevance'))
    research['relevance_status'] = (relevance_research or {}).get('status')
    research['relevance_reason'] = (relevance_research or {}).get('reason')
    research['relevance_model'] = (relevance_research or {}).get('model')
    research['relevance_models_used'] = _safe_list((relevance_research or {}).get('models_used'))
    research['relevance_classifier_models'] = _safe_list((relevance_research or {}).get('classifier_models'))
    research['relevance_component_count'] = len(research['hardware_relevance'])
    research['relevance_researchable_count'] = int((relevance_research or {}).get('researchable_count') or research['relevance_component_count'])
    research['relevance_evaluable_count'] = int((relevance_research or {}).get('evaluable_count') or 0)
    research['relevance_component_research'] = _safe_list((relevance_research or {}).get('component_research'))
    rel_sources = _safe_list((relevance_research or {}).get('sources'))
    sup_sources = _safe_list(research.get('sources'))
    research['sources'] = list(dict.fromkeys([str(x) for x in sup_sources + rel_sources if _text(x)]))[:40]
    research['source_count'] = len(research['sources'])
    if (relevance_research or {}).get('status') in {'OK', 'PARTIAL_RATE_LIMITED'}:
        research['status'] = (relevance_research or {}).get('status')
        research['search_executed'] = True
    research['relevance_attempts'] = _safe_list((relevance_research or {}).get('attempts'))
    attempts = []
    parsed = None
    used = None
    last_error = None
    for candidate in candidates:
        modes = ('strict', 'json') if candidate in STRICT_SCHEMA_MODELS else ('json',)
        for mode in modes:
            try:
                _pace_provider()
                response = _call_analysis(client, candidate, inventory, diagnostic, problems, year, response_mode=mode)
                message = response.choices[0].message if response and response.choices else None
                content = getattr(message, 'content', '') if message is not None else ''
                finish = getattr(response.choices[0], 'finish_reason', None) if response and response.choices else None
                if not _text(content):
                    raise RuntimeError(f'respuesta final vacía (finish_reason={finish})')
                parsed = _extract_json(content)
                if not parsed:
                    raise RuntimeError('respuesta JSON inválida')
                used = candidate
                attempts.append({'model': candidate, 'mode': mode, 'status': 'OK', 'finish_reason': finish})
                break
            except Exception as exc:
                last_error = f'{type(exc).__name__}: {exc}'
                code = _error_status_code(exc)
                attempts.append({'model': candidate, 'mode': mode, 'status': 'ERROR_RATE_LIMIT_429' if code == 429 else 'ERROR', 'http_status': code, 'error': last_error})
                if code == 429:
                    break
        if parsed and used:
            break
        if attempts and attempts[-1].get('http_status') == 429:
            break
    if not parsed or not used:
        # Si la narración falla pero la investigación web sí devolvió evidencia, CorePulse
        # conserva tutoriales/vigencia verificados y construye los pasos desde sus reglas
        # determinísticas. La IA nunca es requisito para reaccionar ante un problema real.
        web_has_evidence = bool(_safe_list(research.get('hardware_relevance')) or any((isinstance(x, dict) and x.get('status') == 'VERIFIED_EXACT' for x in (research.get('tutorials') or {}).values())))
        if web_has_evidence:
            partial = _normalize({}, inventory, diagnostic, problems, research, year=year, model=candidates[0], available=available)
            partial['status'] = 'PARTIAL'
            partial['executive_summary'] = 'La investigación verificable se completó parcialmente; la narración IA no estuvo disponible. Los pasos correctivos provienen de reglas determinísticas de CorePulse.'
            partial['limitations'] = [f'Análisis narrativo no disponible: {last_error}']
            partial.update({'inventory': inventory, 'diagnostic': diagnostic, 'detected_problems': problems, 'model_attempts': attempts, 'generated_at': time.time(), 'env': {'loaded': bool(env_state.get('loaded')), 'loader': env_state.get('loader'), 'ai_runtime': runtime_state}})
            return partial
        r = _fallback_result(inventory, f'Groq no pudo producir un análisis narrativo válido: {last_error}', year=year, model=candidates[0], available=available)
        r['research'] = research
        r.update({'inventory': inventory, 'diagnostic': diagnostic, 'detected_problems': problems, 'model_attempts': attempts, 'env': {'loaded': bool(env_state.get('loaded')), 'loader': env_state.get('loader'), 'ai_runtime': runtime_state}})
        return r
    result = _normalize(parsed, inventory, diagnostic, problems, research, year=year, model=used, available=available)
    result.update({'inventory': inventory, 'diagnostic': diagnostic, 'detected_problems': problems, 'model_attempts': attempts, 'generated_at': time.time(), 'env': {'loaded': bool(env_state.get('loaded')), 'loader': env_state.get('loader'), 'ai_runtime': runtime_state}})
    return result
__all__ = ['analyze_report_with_ai', '_select_model', '_candidate_models', '_problem_cases', '_normalize', '_decorate_problem_priority', 'VERSION', 'POLICY', 'MODEL_PRIORITY']
