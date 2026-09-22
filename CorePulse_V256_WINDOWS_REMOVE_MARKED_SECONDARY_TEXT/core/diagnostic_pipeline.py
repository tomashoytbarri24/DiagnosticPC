"""Integra el diagnóstico completado con el motor de recomendaciones sin reclasificar evidencia."""
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
# Código refactorizado: nombres estables y documentación en español.
import copy
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.recommendation_engine import build_recommendation_pipeline
def _normalize_current_diagnostic(diagnostic: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza la operación `normalize_current_diagnostic` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    result = copy.deepcopy(diagnostic if isinstance(diagnostic, dict) else {})
    findings = result.get('findings')
    if isinstance(findings, list):
        normalized = []
        for item in findings:
            if not isinstance(item, dict):
                continue
            f = copy.deepcopy(item)
            evidence = f.get('evidence')
            if isinstance(evidence, list):
                f['evidence'] = {'evidence_lines': list(evidence)}
            normalized.append(f)
        result['findings'] = normalized
    return result

def integrate_current_diagnostic_pipeline(diagnostic_result: Dict[str, Any], telemetry_snapshot: Dict[str, Any], disks_snapshot: Optional[List[Dict[str, Any]]]=None, *, device_identity: Optional[Dict[str, Any]]=None, output_path: Optional[str]=None) -> Dict[str, Any]:
    """Integra la operación `integrate_current_diagnostic_pipeline` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    original = diagnostic_result if isinstance(diagnostic_result, dict) else {}
    normalized = _normalize_current_diagnostic(original)
    telemetry = telemetry_snapshot if isinstance(telemetry_snapshot, dict) else {}
    disks = disks_snapshot if isinstance(disks_snapshot, list) else []
    pipeline = build_recommendation_pipeline(normalized, telemetry, disks, device_identity=device_identity if isinstance(device_identity, dict) else {})
    pipeline['runtime_integration'] = {'version': VERSION, 'integrated_at': time.time(), 'scope': 'CURRENT_DIAGNOSTIC_ONLY', 'diagnostic_status_original': original.get('overall_status', original.get('status')), 'diagnostic_sample_count_original': original.get('sample_count'), 'diagnostic_duration_seconds_original': original.get('duration_seconds'), 'diagnostic_finish_reason_original': (original.get('adaptive_diagnostic') or {}).get('finish_reason') if isinstance(original.get('adaptive_diagnostic'), dict) else original.get('finish_reason'), 'telemetry_snapshot_attached': bool(telemetry), 'disk_snapshot_count': len(disks), 'history_used_as_current_fault_source': False, 'diagnostic_modified': False, 'external_ai_used': False, 'youtube_link_verified': False}
    status = str(original.get('overall_status', original.get('status', 'UNKNOWN')) or 'UNKNOWN').upper()
    if status == 'NORMAL' and pipeline.get('recommendation_count', 0) != 0:
        raise RuntimeError('CorePulse integrity violation: un diagnóstico NORMAL produjo recomendaciones correctivas.')
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
        tmp.write_text(json.dumps(pipeline, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        os.replace(tmp, path)
        pipeline['runtime_integration']['saved_to'] = str(path)
    return pipeline
