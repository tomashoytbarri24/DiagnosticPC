"""Regresión offline de recuperación transitoria sin mezclar componentes."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import ai_evidence_research as research


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok

component = {
    'id': 'GPU:1',
    'type': 'GPU',
    'name': 'Nebula Accelerator X900',
    'facts': {'manufacturer': 'Nova Silicon', 'vram_gb': 12},
}
other_component = {
    'id': 'GPU:2',
    'type': 'GPU',
    'name': 'Orion Graphics Y500',
    'facts': {'manufacturer': 'Orion Labs', 'vram_gb': 8},
}
reference_row = {
    'component_id': 'GPU:1',
    'component_type': 'GPU',
    'detected_hardware': 'Nebula Accelerator X900',
    'classification': 'ESTANDAR',
    'confidence': 'ALTA',
    'source_count': 8,
    'research_status': 'OK',
    'decision_score': 2.0,
    'evidence_axes': {'primary_position': 'MEETS', 'secondary_position': 'MEETS'},
    'sources': ['https://docs.novasilicon.example/x900'],
}
cache = {
    'schema': research._RELEVANCE_CACHE_SCHEMA,
    'entries': {
        research._cache_key(component, 2026): {
            'saved_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'row': reference_row,
        }
    },
    'stability_reference': {},
}
failed = {
    'component_id': 'GPU:1',
    'component_type': 'GPU',
    'detected_hardware': 'Nebula Accelerator X900',
    'classification': 'NO_EVALUABLE',
    'confidence': 'BAJA',
    'source_count': 8,
    'research_status': 'INSUFFICIENT_COMPARATIVE_CONTEXT',
    'extraction_status': 'ERROR',
    'extraction_error': 'synthetic transient parser error',
    'extraction_attempts': [{'status': 'ERROR'}],
}
live_rows = {'GPU:1': dict(failed)}
recovered = research._recover_failed_live_rows(cache, [component], live_rows, 2026)
row = live_rows['GPU:1']

other_live = {'GPU:2': dict(failed, component_id='GPU:2', detected_hardware='Orion Graphics Y500')}
other_recovered = research._recover_failed_live_rows(cache, [other_component], other_live, 2026)

prompt = research._compact_extractor_prompt({
    'component_type': 'GPU', 'detected_hardware': 'Nebula Accelerator X900', 'facts': {'vram_gb': 12}
}, 2026, [])

results = [
    check('same_component_reference_recovers_transient_failure', recovered == 1 and row.get('classification') == 'ESTANDAR'),
    check('recovery_caps_high_confidence_to_medium', row.get('confidence') == 'MEDIA'),
    check('recovery_is_traceable_not_cache_hit', row.get('research_status') == 'RECOVERED_VERIFIED_REFERENCE' and row.get('cache_hit') is False),
    check('different_component_cannot_inherit_reference', other_recovered == 0 and other_live['GPU:2'].get('classification') == 'NO_EVALUABLE'),
    check('compact_repair_prompt_uses_runtime_identity', 'Nebula Accelerator X900' in prompt),
]
print('\nRESULTADO:', 'PASS' if all(results) else 'FAIL')
raise SystemExit(0 if all(results) else 1)
