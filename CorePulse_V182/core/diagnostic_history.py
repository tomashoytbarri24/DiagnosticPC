"""Historial/comparación ligera del Diagnóstico Completo.

V150 compara únicamente estados derivados del mismo motor determinista de
CorePulse. No crea scores nuevos ni usa el historial como fuente de fallos
actuales; sólo explica si el estado cambió respecto del diagnóstico completo
anterior guardado localmente.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from core.diagnostic_summary import build_component_assessments
from core.runtime_paths import diagnostics_dir


def load_previous_complete_result(current_path: str | None = None) -> Optional[Dict[str, Any]]:
    root = Path(diagnostics_dir())
    try:
        files = sorted(root.glob('diagnostic_complete_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        return None
    current = Path(current_path).resolve() if current_path else None
    for path in files:
        try:
            if current is not None and path.resolve() == current:
                continue
            payload = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        complete = payload.get('complete_diagnostic') if isinstance(payload, dict) else None
        if not isinstance(complete, dict):
            continue
        if (str(complete.get('status') or '').upper() not in {'COMPLETE', 'PARTIAL'}
                or complete.get('finalized') is False or complete.get('cancelled_by_user')):
            continue
        return payload
    return None


def _status_map(result: Dict[str, Any]) -> Dict[str, str]:
    return {
        str(item.get('key')): str(item.get('status') or 'NO_EVALUABLE').upper()
        for item in build_component_assessments(result if isinstance(result, dict) else {})
        if isinstance(item, dict) and item.get('key')
    }


def build_diagnostic_comparison(current: Dict[str, Any], previous: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(previous, dict):
        return {
            'available': False,
            'policy': 'INFORMATIONAL_ONLY_NOT_CURRENT_FAULT_SOURCE',
            'component_changes': [],
        }
    now_map = _status_map(current)
    prev_map = _status_map(previous)
    labels = {
        'cpu': 'CPU', 'gpu': 'GPU', 'ram': 'RAM', 'storage': 'Almacenamiento',
        'battery': 'Batería', 'windows': 'Windows',
    }
    changes = []
    for key in ('cpu', 'gpu', 'ram', 'storage', 'battery', 'windows'):
        before = prev_map.get(key, 'NO_EVALUABLE')
        after = now_map.get(key, 'NO_EVALUABLE')
        if before != after:
            changes.append({
                'key': key,
                'title': labels[key],
                'previous': before,
                'current': after,
            })
    previous_complete = previous.get('complete_diagnostic') if isinstance(previous.get('complete_diagnostic'), dict) else {}
    return {
        'available': True,
        'previous_started_at': previous.get('started_at'),
        'previous_overall_status': str(previous.get('overall_status') or 'NO_EVALUABLE').upper(),
        'current_overall_status': str(current.get('overall_status') or 'NO_EVALUABLE').upper(),
        'previous_complete_status': str(previous_complete.get('status') or 'UNKNOWN').upper(),
        'component_changes': changes,
        'unchanged_components': max(0, 6 - len(changes)),
        'policy': 'INFORMATIONAL_ONLY_NOT_CURRENT_FAULT_SOURCE',
        'history_used_as_current_fault_source': False,
    }
