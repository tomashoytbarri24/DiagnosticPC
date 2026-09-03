"""Carga de forma segura la configuración y variables de entorno utilizadas por CorePulse."""
# Código refactorizado: nombres estables y documentación en español.
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
from pathlib import Path
from typing import Dict
import os
import re
import sys
ENV_POLICY = 'RUNTIME_DOTENV_ONLY_NO_ENV_EXAMPLE_DEPENDENCY'
ENV_EXAMPLE_POLICY = 'OPTIONAL_DOCUMENTATION_ONLY_NEVER_RUNTIME_INPUT'
_LOADED = False
_STATUS: Dict[str, object] = {'loaded': False, 'path': None, 'loader': None, 'python_dotenv_available': False, 'groq_key_detected': False}
_ENV_LINE = re.compile('^(?:export\\s+)?([A-Za-z_][A-Za-z0-9_]*)\\s*=\\s*(.*)$')

def _candidate_env_files() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.getenv('COREPULSE_ENV_FILE', '').strip()
    if explicit:
        try:
            candidates.append(Path(explicit).expanduser().resolve())
        except Exception:
            candidates.append(Path(explicit).expanduser())
    if getattr(sys, 'frozen', False):
        try:
            candidates.append(Path(sys.executable).resolve().parent / '.env')
        except Exception:
            pass
    try:
        candidates.append(Path(__file__).resolve().parent.parent / '.env')
    except Exception:
        pass
    try:
        candidates.append(Path.cwd() / '.env')
    except Exception:
        pass
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique

def _parse_env_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ''
    if value[0:1] in {'"', "'"}:
        q = value[0]
        end = value.find(q, 1)
        if end >= 1:
            return value[1:end]
        return value[1:]
    value = re.split('\\s+#', value, maxsplit=1)[0].strip()
    return value

def _load_builtin(path: Path) -> bool:
    try:
        text = path.read_text(encoding='utf-8-sig')
    except Exception:
        return False
    applied = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        match = _ENV_LINE.match(line)
        if not match:
            continue
        key, raw_value = (match.group(1), match.group(2))
        if key in os.environ:
            continue
        os.environ[key] = _parse_env_value(raw_value)
        applied = True
    return applied or path.is_file()

def load_corepulse_env() -> Dict[str, object]:
    """Carga la operación `load_corepulse_env` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    global _LOADED, _STATUS
    if _LOADED and (bool(_STATUS.get('loaded')) or bool(os.getenv('GROQ_API_KEY', '').strip())):
        _STATUS['groq_key_detected'] = bool(os.getenv('GROQ_API_KEY', '').strip())
        return dict(_STATUS)
    _LOADED = True
    load_dotenv = None
    try:
        from dotenv import load_dotenv as _load_dotenv
        load_dotenv = _load_dotenv
        _STATUS['python_dotenv_available'] = True
    except Exception:
        _STATUS['python_dotenv_available'] = False
    for env_path in _candidate_env_files():
        try:
            if not env_path.is_file():
                continue
            loaded = False
            if load_dotenv is not None:
                try:
                    load_dotenv(dotenv_path=env_path, override=False, encoding='utf-8-sig')
                    loaded = True
                    _STATUS['loader'] = 'python-dotenv'
                except Exception:
                    loaded = False
            if not loaded:
                loaded = _load_builtin(env_path)
                if loaded:
                    _STATUS['loader'] = 'builtin'
            if loaded:
                _STATUS['loaded'] = True
                _STATUS['path'] = str(env_path)
                break
        except Exception:
            continue
    _STATUS['groq_key_detected'] = bool(os.getenv('GROQ_API_KEY', '').strip())
    return dict(_STATUS)



def ai_runtime_status() -> Dict[str, object]:
    """Devuelve el estado de configuración IA sin exponer credenciales."""
    state = load_corepulse_env()
    enabled = str(os.getenv('COREPULSE_AI_ENABLED', '1')).strip().lower() not in {'0', 'false', 'off', 'no'}
    web_enabled = str(os.getenv('COREPULSE_AI_WEB_RESEARCH', '1')).strip().lower() not in {'0', 'false', 'off', 'no'}
    key_present = bool(os.getenv('GROQ_API_KEY', '').strip())
    requested_model = str(os.getenv('COREPULSE_GROQ_MODEL', 'openai/gpt-oss-120b')).strip() or 'openai/gpt-oss-120b'
    if not enabled:
        status = 'DISABLED'
        reason = 'COREPULSE_AI_ENABLED está desactivado.'
    elif not key_present:
        status = 'MISSING_KEY'
        reason = 'No se detectó GROQ_API_KEY en variables de entorno ni en el .env local.'
    elif not web_enabled:
        status = 'AI_READY_WEB_DISABLED'
        reason = 'La IA narrativa está configurada, pero COREPULSE_AI_WEB_RESEARCH está desactivado.'
    else:
        status = 'CONFIGURED'
        reason = 'Configuración local presente. La disponibilidad real del proveedor se valida al ejecutar el análisis.'
    return {
        'status': status,
        'reason': reason,
        'ai_enabled': enabled,
        'web_research_enabled': web_enabled,
        'groq_key_detected': key_present,
        'requested_model': requested_model,
        'env_loaded': bool(state.get('loaded')),
        'env_path': state.get('path'),
        'env_loader': state.get('loader'),
        'secret_exposed': False,
    }
def env_status() -> Dict[str, object]:
    status = dict(_STATUS)
    status['groq_key_detected'] = bool(os.getenv('GROQ_API_KEY', '').strip())
    return status
load_corepulse_env()
__all__ = ['load_corepulse_env', 'env_status', 'ai_runtime_status', 'VERSION', 'ENV_POLICY', 'ENV_EXAMPLE_POLICY']
