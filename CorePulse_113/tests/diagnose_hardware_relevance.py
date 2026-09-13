"""Diagnóstico live de vigencia por componente. No imprime ni expone GROQ_API_KEY."""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.ai_evidence_research import research_hardware_relevance
from core.ai_report_engine import _sanitized_inventory
from core.env_config import ai_runtime_status, load_corepulse_env

load_corepulse_env()
status = ai_runtime_status()
print('CorePulse · Diagnóstico de vigencia de hardware')
print('-----------------------------------------------')
print('Estado configuración   :', status.get('status'))
print('IA habilitada          :', status.get('ai_enabled'))
print('Web research           :', status.get('web_research_enabled'))
print('GROQ_API_KEY detectada :', status.get('groq_key_detected'))
print('Modelo solicitado      :', status.get('requested_model'))
print('Archivo .env cargado   :', status.get('env_loaded'))
if not status.get('groq_key_detected'):
    raise SystemExit('RESULTADO: FAIL - falta GROQ_API_KEY local')
if not status.get('ai_enabled'):
    raise SystemExit('RESULTADO: FAIL - COREPULSE_AI_ENABLED está desactivado')
if not status.get('web_research_enabled'):
    raise SystemExit('RESULTADO: FAIL - COREPULSE_AI_WEB_RESEARCH está desactivado')

inventory = _sanitized_inventory({}, [])
components = inventory.get('components') or []
print('Componentes detectados:', len(components))
for component in components:
    print(f"  - {component.get('id')}: {component.get('name')}")

try:
    from groq import Groq
    client = Groq(api_key=os.getenv('GROQ_API_KEY'), timeout=20.0)
    available = sorted({str(getattr(item, 'id', '') or '') for item in client.models.list().data if getattr(item, 'id', None)})
except Exception as exc:
    raise SystemExit(f'RESULTADO: FAIL - proveedor: {type(exc).__name__}: {exc}')

print('\nInvestigación live por componente:')
result = research_hardware_relevance(
    api_key=os.getenv('GROQ_API_KEY', ''),
    available_models=available,
    components=components,
    year=datetime.now().year,
    progress_callback=lambda line: print(line),
)
print('\nResumen final')
print('Estado            :', result.get('status'))
print('Evaluables        :', f"{result.get('evaluable_count')}/{result.get('researchable_count')}")
print('Búsquedas web     :', f"{result.get('web_search_calls')}/{result.get('web_search_budget')}")
print('Ruta              :', result.get('request_mode'))
print('Cache hits        :', result.get('cache_hits', 0))
for row in result.get('hardware_relevance') or []:
    print(f"{row.get('component_id'):12} | {row.get('classification'):25} | {row.get('confidence'):5} | fuentes={row.get('source_count',0)} | {row.get('research_status')}")
    print(f"             extractor: {row.get('extraction_status','N/A')} · modelo={row.get('extractor_model') or 'N/A'}")
    if row.get('confidence_basis'):
        print('             confianza:', row.get('confidence_basis'))
    axes = row.get('evidence_axes') if isinstance(row.get('evidence_axes'), dict) else {}
    if axes.get('evidence_conflict'):
        print('             conflicto:', axes.get('conflict_reason') or 'SI, sin detalle textual')
print('RESULTADO          : PASS')
