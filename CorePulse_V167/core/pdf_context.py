"""Construye el contexto consistente que utiliza el reporte PDF a partir del diagnóstico congelado."""
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
# Código refactorizado: nombres estables y documentación en español.
import copy
from typing import Any, Dict, List
PIPELINE_KEYS = ('_intelligent_recommendations', 'recommendation_pipeline', 'intelligent_recommendations', 'current_diagnostic_recommendations', '_recommendation_pipeline')
NORMAL_STATES = {'NORMAL', 'PASS', 'OK', 'OPTIMAL', 'OPTIMO', 'ÓPTIMO'}
ACTIONABLE_STATES = {'WARNING', 'ADVERTENCIA', 'CRITICAL', 'CRITICO', 'CRÍTICO'}

def _status(diagnostic: Dict[str, Any]) -> str:
    for key in ('overall_status', 'overall', 'status'):
        value = diagnostic.get(key)
        if value:
            return str(value).strip().upper()
    return 'UNKNOWN'

def extract_current_pipeline(diagnostic: Any) -> Dict[str, Any]:
    if not isinstance(diagnostic, dict):
        raise RuntimeError('CorePulse PDF: diagnostic_result no es un diccionario válido.')
    for key in PIPELINE_KEYS:
        value = diagnostic.get(key)
        if isinstance(value, dict):
            return value
    raise RuntimeError('CorePulse PDF: el diagnóstico actual no contiene el pipeline de recomendaciones vigente. Completa un diagnóstico nuevo antes de exportar.')

def build_strict_pdf_context(diagnostic: Any) -> Dict[str, Any]:
    diagnostic = diagnostic if isinstance(diagnostic, dict) else {}
    diag_status = _status(diagnostic)
    pipeline = extract_current_pipeline(diagnostic)
    pipe_status = str(pipeline.get('diagnostic_status') or 'UNKNOWN').strip().upper()
    runtime = pipeline.get('runtime_integration') if isinstance(pipeline.get('runtime_integration'), dict) else {}
    runtime_status = str(runtime.get('diagnostic_status_original') or pipe_status).strip().upper()
    scope = str(runtime.get('scope') or pipeline.get('scope') or 'CURRENT_DIAGNOSTIC_ONLY').strip().upper()
    recs = pipeline.get('recommendations') if isinstance(pipeline.get('recommendations'), list) else []
    infos = pipeline.get('informational_findings') if isinstance(pipeline.get('informational_findings'), list) else []
    rec_count = int(pipeline.get('recommendation_count', len(recs)) or 0)
    info_count = int(pipeline.get('informational_count', len(infos)) or 0)
    errors = []
    if diag_status != pipe_status:
        errors.append(f'diagnostic_result={diag_status} != pipeline={pipe_status}')
    if runtime_status not in {'', 'NONE', 'UNKNOWN'} and runtime_status != diag_status:
        errors.append(f'runtime_original={runtime_status} != diagnostic_result={diag_status}')
    if scope != 'CURRENT_DIAGNOSTIC_ONLY':
        errors.append(f'scope inválido: {scope}')
    if rec_count != len(recs):
        errors.append(f'recommendation_count={rec_count} != len(recommendations)={len(recs)}')
    if info_count != len(infos):
        errors.append(f'informational_count={info_count} != len(informational_findings)={len(infos)}')
    if diag_status in NORMAL_STATES and rec_count != 0:
        errors.append('diagnóstico NORMAL contiene recomendaciones correctivas')
    if diag_status in ACTIONABLE_STATES and rec_count < 1:
        errors.append('diagnóstico WARNING/CRITICAL no contiene recomendación actionable')
    if runtime.get('history_used_as_current_fault_source') is True:
        errors.append('historial del agente fue usado como fuente de falla actual')
    if runtime.get('external_ai_used') is True:
        errors.append('IA externa fue usada antes de la etapa autorizada')
    if errors:
        raise RuntimeError('CorePulse PDF consistency violation: ' + ' | '.join(errors))
    normalized = []
    for rec in recs:
        if not isinstance(rec, dict):
            continue
        normalized.append({'recommendation_id': rec.get('recommendation_id') or 'N/A', 'component': rec.get('component') or 'GENERAL', 'severity': rec.get('severity') or diag_status, 'title': rec.get('title') or 'Recomendación basada en evidencia', 'finding': rec.get('finding') or 'N/A', 'evidence': copy.deepcopy(rec.get('evidence') or {}), 'steps': list(rec.get('steps') or []), 'supplies': list(rec.get('supplies') or []), 'tutorial_query': rec.get('tutorial_query'), 'tutorial_verified': bool(rec.get('tutorial_verified', False)), 'evidence_bound': bool(rec.get('evidence_bound', False)), 'source': rec.get('source') or 'CURRENT_DIAGNOSTIC_ONLY'})
    return {'version': VERSION, 'diagnostic_status': diag_status, 'pipeline_status': pipe_status, 'scope': scope, 'recommendations': normalized, 'informational_findings': copy.deepcopy(infos), 'recommendation_count': len(normalized), 'informational_count': len(infos), 'no_corrective_actions_required': diag_status in NORMAL_STATES and (not normalized), 'history_used_as_current_fault_source': False, 'external_ai_used': False, 'youtube_links_verified': all((bool(x.get('tutorial_verified')) for x in normalized)) if normalized else False, 'tutorial_policy': 'PENDING_EXTERNAL_VERIFICATION', 'runtime_integration': copy.deepcopy(runtime)}
