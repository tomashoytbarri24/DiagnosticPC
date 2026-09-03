"""Diagnóstico seguro de configuración IA/CorePulse. No imprime la API key."""
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
from core.env_config import ai_runtime_status

state = ai_runtime_status()
print('CorePulse · Diagnóstico del runtime de IA')
print('---------------------------------------')
print('Estado configuración :', state.get('status'))
print('IA habilitada        :', state.get('ai_enabled'))
print('Web research         :', state.get('web_research_enabled'))
print('GROQ_API_KEY detectada:', state.get('groq_key_detected'))
print('Modelo solicitado    :', state.get('requested_model'))
print('Archivo .env cargado :', state.get('env_loaded'))
print('Ruta .env            :', state.get('env_path') or 'N/A')
print('Motivo               :', state.get('reason'))

if not state.get('groq_key_detected'):
    print('\n[ACCIÓN] Copia .env.example a .env y configura GROQ_API_KEY localmente.')
    raise SystemExit(2)

try:
    from groq import Groq
    client = Groq(api_key=os.getenv('GROQ_API_KEY'), timeout=20.0)
    models = sorted({str(getattr(x, 'id', '') or '') for x in client.models.list().data if getattr(x, 'id', None)})
    requested = str(state.get('requested_model') or '')
    research = [x for x in ('groq/compound-mini', 'groq/compound') if x in models]
    narrative = [x for x in (requested, 'openai/gpt-oss-120b', 'openai/gpt-oss-20b') if x and x in models]
    print('\nProveedor Groq       : CONECTADO')
    print('Modelos descubiertos :', len(models))
    print('Narrativa compatible :', ', '.join(dict.fromkeys(narrative)) or 'NINGUNO')
    print('Web compatible       :', ', '.join(research) or 'NINGUNO')
    ok = bool(narrative and (research or not state.get('web_research_enabled')))
    print('RESULTADO             :', 'PASS' if ok else 'PARTIAL')
    raise SystemExit(0 if ok else 3)
except SystemExit:
    raise
except Exception as exc:
    print('\nProveedor Groq       : ERROR')
    print('Error                 :', f'{type(exc).__name__}: {exc}')
    print('RESULTADO             : FAIL')
    raise SystemExit(4)
