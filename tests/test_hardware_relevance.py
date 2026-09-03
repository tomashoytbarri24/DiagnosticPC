"""Regresión offline de investigación universal, confianza y vigencia estable."""
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import ai_evidence_research as research


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok

component = {
    'component_id': 'GPU:0',
    'component_type': 'GPU',
    'detected_hardware': 'Nebula Accelerator X900',
    'facts': {'manufacturer': 'Nova Silicon', 'vram_gb': 12},
}
strategies = research._component_search_strategies(component, 2026)
strategy_text = ' '.join(item.get('prompt', '') for item in strategies)
quality = research._source_quality(
    {'url': 'https://docs.novasilicon.com/x900/specifications', 'title': 'X900 specifications', 'content': 'Nebula Accelerator X900 GPU benchmark comparison 2026'},
    component,
)
profile = {
    'source_count': 8, 'independent_hosts': 5, 'strong_hosts': 4,
    'tier_counts': {'A': 3, 'B': 2, 'C': 3}, 'quality_points': 18,
    'component_sources': 6, 'context_sources': 6, 'sufficient': True,
}
axes = {
    'primary_position': 'MEETS', 'secondary_position': 'ABOVE', 'tertiary_position': 'MEETS',
    'material_limitation': 'NO', 'evidence_conflict': False,
}
conf = research._confidence_assessment(profile, axes, 'ESTANDAR', 'GPU')
decision = research._deterministic_relevance_decision('GPU', axes, profile)
weak_optimal_axes = dict(axes, primary_position='WELL_ABOVE')
weak_profile = dict(profile, tier_counts={'A': 0, 'B': 1, 'C': 7}, strong_hosts=1, quality_points=9)
weak_decision = research._deterministic_relevance_decision('GPU', weak_optimal_axes, weak_profile)

source = (ROOT / 'core' / 'ai_evidence_research.py').read_text(encoding='utf-8').lower()
known_test_hardware = ('ge66', '10750h', 'rtx 2070', 'mzvlb512')

results = [
    check('query_uses_runtime_component_identity', 'Nebula Accelerator X900' in strategy_text),
    check('query_uses_runtime_manufacturer_hint', 'nova' in strategy_text.lower()),
    check('dynamic_official_source_is_tier_a', quality.get('tier') == 'A'),
    check('strong_consistent_evidence_can_be_high', conf.get('confidence') == 'ALTA'),
    check('primary_meets_anchors_at_standard', decision.get('classification') == 'ESTANDAR'),
    check('optimal_is_gated_by_evidence_quality', weak_decision.get('classification') != 'OPTIMO'),
    check('runtime_has_no_test_machine_hardcoding', not any(token in source for token in known_test_hardware)),
]
print('\nRESULTADO:', 'PASS' if all(results) else 'FAIL')
raise SystemExit(0 if all(results) else 1)
