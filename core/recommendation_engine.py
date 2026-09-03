"""Genera recomendaciones únicamente desde problemas confirmados por el diagnóstico actual."""
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
# Código refactorizado: nombres estables y documentación en español.
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import json
import math
import time
ALLOWED_STATUS = {'NORMAL', 'INFO', 'INFORMATIVO', 'WARNING', 'ADVERTENCIA', 'CRITICAL', 'CRITICO', 'CRÍTICO'}
ACTIONABLE = {'WARNING', 'ADVERTENCIA', 'CRITICAL', 'CRITICO', 'CRÍTICO'}

def _norm_status(v: Any) -> str:
    s = str(v or '').strip().upper()
    return s if s in ALLOWED_STATUS else 'INFO'

def _safe_text(v: Any) -> str:
    return str(v).strip() if v is not None else ''

def _finding_component(f: Dict[str, Any]) -> str:
    for key in ('component', 'metric', 'category', 'subsystem', 'name'):
        val = _safe_text(f.get(key))
        if val:
            return val.upper()
    return 'GENERAL'

def _finding_status(f: Dict[str, Any]) -> str:
    for key in ('status', 'severity', 'level', 'state'):
        if key in f:
            return _norm_status(f.get(key))
    return 'INFO'

def _finding_message(f: Dict[str, Any]) -> str:
    for key in ('message', 'result', 'title', 'summary', 'reason', 'description'):
        val = _safe_text(f.get(key))
        if val:
            return val
    return 'Hallazgo reportado por el diagnóstico actual.'

def _extract_findings(diagnostic: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for key in ('findings', 'hallazgos', 'checks', 'results', 'components'):
        raw = diagnostic.get(key)
        if isinstance(raw, list):
            candidates.extend((x for x in raw if isinstance(x, dict)))
        elif isinstance(raw, dict):
            for name, item in raw.items():
                if isinstance(item, dict):
                    x = dict(item)
                    x.setdefault('component', name)
                    candidates.append(x)
    return candidates

def _evidence_from_finding(f: Dict[str, Any]) -> Dict[str, Any]:
    evidence: Dict[str, Any] = {}
    for key in ('value', 'average', 'avg', 'max', 'maximum', 'min', 'minimum', 'threshold', 'warning_threshold', 'critical_threshold', 'duration_seconds', 'time_seconds', 'samples', 'sample_count', 'coverage', 'source', 'sensor', 'quality', 'timestamp', 'distance_to_tjmax', 'distance_to_tjmax_min_c'):
        if key in f and f.get(key) is not None:
            evidence[key] = f.get(key)
    nested = f.get('evidence')
    if isinstance(nested, dict):
        for k, v in nested.items():
            if v is not None:
                evidence.setdefault(k, v)
    return evidence

def _telemetry_evidence(telemetry: Dict[str, Any], component: str) -> Dict[str, Any]:
    t = telemetry if isinstance(telemetry, dict) else {}
    metrics = t.get('_metrics') if isinstance(t.get('_metrics'), dict) else {}
    c = component.upper()
    keys: List[str] = []
    if 'CPU' in c:
        keys = ['cpu_usage', 'cpu_ghz', 'cpu_temp']
    elif 'RAM' in c or 'MEM' in c:
        keys = ['ram_usage']
    elif 'GPU' in c:
        keys = ['gpu_usage', 'gpu_temp', 'gpu_vram_gb']
    result: Dict[str, Any] = {}
    for key in keys:
        m = metrics.get(key)
        if isinstance(m, dict):
            result[key] = {'value': m.get('value'), 'unit': m.get('unit'), 'source': m.get('source'), 'sensor': m.get('sensor'), 'quality': m.get('quality'), 'timestamp': m.get('timestamp')}
    return result

def _recommendation_template(component: str, finding: str='') -> Dict[str, Any]:
    c = component.upper()
    finding_low = _safe_text(finding).lower()
    if 'CPU' in c:
        return {
            'title': 'Revisar condiciones térmicas y carga de CPU',
            'steps': [
                'Confirmar que las entradas y salidas de aire estén libres de obstrucciones.',
                'Revisar procesos con uso elevado de CPU si la carga permanece alta.',
                'Repetir el diagnóstico en el mismo contexto para confirmar persistencia.',
                'Si la condición térmica persiste, seguir el procedimiento de mantenimiento del modelo exacto para ventiladores, disipador y material térmico, o recurrir a servicio técnico calificado.',
            ],
            'supplies': ['Ninguno para la verificación inicial.', 'Aire comprimido apto para electrónica y material térmico solo si el procedimiento exacto del fabricante/modelo contempla desmontaje.'],
            'tutorial_action': 'cooling fan cleaning heatsink thermal paste disassembly',
        }
    if 'RAM' in c or 'MEM' in c:
        return {
            'title': 'Reducir presión real de memoria',
            'steps': [
                'Revisar en el Administrador de tareas qué procesos consumen más memoria.',
                'Cerrar únicamente aplicaciones innecesarias y repetir la medición en la misma carga.',
                'Revisar programas de inicio y cargas residentes que mantengan presión sostenida.',
                'Si el uso habitual sigue alcanzando el criterio de advertencia, verificar slots, memoria soldada y capacidad máxima del modelo exacto antes de evaluar una ampliación.',
            ],
            'supplies': ['Ninguno para la optimización por software.', 'Módulo RAM compatible solo después de verificar la actualizabilidad del modelo exacto.'],
            'tutorial_action': 'RAM upgrade memory slot disassembly',
        }
    if 'GPU' in c:
        return {
            'title': 'Verificar carga y condiciones de GPU',
            'steps': [
                'Confirmar si la carga observada corresponde a una aplicación o juego activo.',
                'Repetir la prueba en el mismo contexto GAME/DESKTOP.',
                'Si existe una advertencia térmica, revisar ventilación, ventiladores y disipador siguiendo el procedimiento del modelo exacto.',
                'No aplicar overclock, undervolt ni offsets automáticos sin validación específica del hardware.',
            ],
            'supplies': ['Ninguno para verificación inicial.', 'Herramientas/material térmico solo si el procedimiento exacto requiere mantenimiento físico.'],
            'tutorial_action': 'GPU cooling fan heatsink thermal pad disassembly',
        }
    if any((x in c for x in ('STORAGE', 'ALMAC', 'DISK', 'SSD'))):
        if 'espacio' in finding_low or 'ocupaci' in finding_low or 'margen' in finding_low:
            return {
                'title': 'Recuperar espacio libre de almacenamiento',
                'steps': [
                    'Revisar archivos temporales y contenido innecesario con herramientas seguras.',
                    'Identificar archivos o aplicaciones de gran tamaño antes de borrar contenido personal.',
                    'Mantener margen libre suficiente para actualizaciones, temporales y paginación.',
                    'Si la capacidad sigue siendo insuficiente, verificar interfaz, formato, slots y compatibilidad del modelo exacto antes de ampliar o reemplazar la unidad.',
                ],
                'supplies': ['Ninguno para liberar espacio por software.', 'Unidad de respaldo antes de una migración o reemplazo.'],
                'tutorial_action': 'SSD upgrade M.2 installation storage replacement disassembly',
            }
        return {
            'title': 'Revisar almacenamiento según evidencia S.M.A.R.T.',
            'steps': [
                'Respaldar información importante si el diagnóstico reporta una condición crítica o degradación real.',
                'Verificar temperatura, vida útil y espacio disponible reportados por la unidad.',
                'Repetir la prueba para confirmar persistencia antes de recomendar reemplazo.',
                'Usar la herramienta oficial del fabricante cuando exista para una comprobación adicional.',
            ],
            'supplies': ['Unidad de respaldo si se requiere proteger datos.'],
            'tutorial_action': 'SSD access replacement M.2 disassembly',
        }
    if 'BAT' in c or 'BATER' in c:
        return {
            'title': 'Revisar condición de batería',
            'steps': [
                'Comparar capacidad de diseño y capacidad de carga completa reportadas.',
                'Observar autonomía y estabilidad de carga en uso normal.',
                'Consultar el procedimiento oficial del modelo exacto si existe una advertencia real.',
            ],
            'supplies': ['Ninguno para diagnóstico inicial.'],
            'tutorial_action': 'battery replacement disassembly',
        }
    return {
        'title': 'Revisar el hallazgo actual',
        'steps': ['Repetir el diagnóstico en el mismo contexto.', 'Confirmar que la evidencia siga presente.', 'Aplicar únicamente acciones compatibles con el componente y fabricante.'],
        'supplies': ['N/A'],
        'tutorial_action': 'maintenance troubleshooting',
    }


def _tutorial_query(identity: Dict[str, Any], component: str, finding: str, action: str) -> Optional[str]:
    manufacturer = _safe_text(identity.get('manufacturer'))
    model = _safe_text(identity.get('model') or identity.get('device_model'))
    parts = [manufacturer, model, component, _safe_text(finding), _safe_text(action), 'tutorial']
    query = ' '.join(x for x in parts if x).strip()
    return query or None

@dataclass
class Recommendation:
    recommendation_id: str
    component: str
    severity: str
    title: str
    finding: str
    evidence: Dict[str, Any]
    steps: List[str]
    supplies: List[str]
    tutorial_query: Optional[str]
    tutorial_verified: bool
    evidence_bound: bool
    source: str

def build_recommendation_pipeline(diagnostic: Dict[str, Any], telemetry: Dict[str, Any], disks=None, *, device_identity=None) -> Dict[str, Any]:
    """Construye la operación `build_recommendation_pipeline` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    diag = diagnostic if isinstance(diagnostic, dict) else {}
    tele = telemetry if isinstance(telemetry, dict) else {}
    identity = device_identity if isinstance(device_identity, dict) else {}
    findings = _extract_findings(diag)
    recommendations: List[Recommendation] = []
    informational: List[Dict[str, Any]] = []
    for idx, f in enumerate(findings, start=1):
        component = _finding_component(f)
        status = _finding_status(f)
        message = _finding_message(f)
        evidence = _evidence_from_finding(f)
        evidence['telemetry_trace'] = _telemetry_evidence(tele, component)
        if status not in ACTIONABLE:
            informational.append({'component': component, 'status': status, 'message': message, 'evidence': evidence})
            continue
        tpl = _recommendation_template(component, message)
        query = _tutorial_query(identity, component, message, tpl.get('tutorial_action') or 'maintenance')
        recommendations.append(Recommendation(recommendation_id=f'REC-{idx:03d}', component=component, severity=status, title=tpl['title'], finding=message, evidence=evidence, steps=tpl['steps'], supplies=tpl['supplies'], tutorial_query=query, tutorial_verified=False, evidence_bound=True, source='CURRENT_DIAGNOSTIC_ONLY'))
    overall = _safe_text(diag.get('overall_status') or diag.get('status') or 'UNKNOWN').upper()
    passed = overall in {'NORMAL', 'PASS', 'OK', 'OPTIMAL', 'OPTIMO', 'ÓPTIMO'} and (not recommendations)
    return {'version': VERSION, 'created_at': time.time(), 'policy': {'current_diagnostic_only': True, 'historical_alerts_do_not_create_current_faults': True, 'no_fabricated_faults': True, 'no_fabricated_thresholds': True, 'no_fabricated_sensor_values': True, 'youtube_links_must_be_verified_externally': True}, 'diagnostic_status': overall, 'passed_current_diagnostic': passed, 'recommendations': [asdict(x) for x in recommendations], 'informational_findings': informational, 'recommendation_count': len(recommendations), 'informational_count': len(informational)}

def save_pipeline_json(result: Dict[str, Any], path: str) -> str:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    return path
