"""Investiga y valida evidencia web para tutoriales y vigencia del hardware sin inventar información."""
# Código refactorizado: nombres estables y documentación en español.
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
from typing import Any, Dict, Iterable, List, Optional
import json
import os
import re
import urllib.parse
import urllib.request
from core.hardware_policy import (
    component_identity_specific as _universal_identity_specific,
    component_brand_tokens, host_looks_official, device_support_target,
)
RESEARCH_MODELS = ('groq/compound-mini', 'groq/compound')
BROWSER_RESEARCH_MODELS = ('openai/gpt-oss-120b', 'openai/gpt-oss-20b')
NOISY_SEARCH_DOMAINS = ('wikipedia.org', 'reddit.com', 'quora.com', 'facebook.com', 'instagram.com', 'tiktok.com', 'pinterest.com', 'edmunds.com', 'exa.ai')
_URL_RE = re.compile('https?://[^\\s\\]\\[<>{}"\\\']+', re.I)

def _text(value: Any, default: str='') -> str:
    return default if value is None else str(value).strip()

def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    raw = _text(text)
    if not raw:
        return None
    raw = re.sub('^```(?:json)?\\s*|\\s*```$', '', raw, flags=re.I | re.S).strip()
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

def _tool_records(message: Any) -> List[Dict[str, Any]]:
    """Gestiona la operación `tool_records` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    records: List[Dict[str, Any]] = []
    tools = getattr(message, 'executed_tools', None) or []
    for tool in tools:
        if isinstance(tool, dict):
            getter = tool.get
        else:
            getter = lambda key, default=None, _tool=tool: getattr(_tool, key, default)
        records.append({'type': _text(getter('type')).lower(), 'arguments': getter('arguments'), 'output': getter('output'), 'search_results': getter('search_results')})
    return records

def _tool_evidence(message: Any) -> str:
    chunks: List[str] = []
    for tool in _tool_records(message):
        for key in ('output', 'search_results', 'arguments'):
            value = tool.get(key)
            if value in (None, '', [], {}):
                continue
            if isinstance(value, (dict, list)):
                try:
                    chunks.append(json.dumps(value, ensure_ascii=False))
                    continue
                except Exception:
                    pass
            chunks.append(str(value))
    return '\n'.join(chunks)

def _tool_trace(message: Any) -> Dict[str, Any]:
    records = _tool_records(message)
    types = [_text(x.get('type')).lower() for x in records if _text(x.get('type'))]
    search_executed = any((t in {'search', 'web_search'} or 'search' in t for t in types))
    visit_executed = any((t in {'visit', 'visit_website'} or 'visit' in t for t in types))
    evidence = _tool_evidence(message)
    return {'executed_tools_count': len(records), 'tool_types': types, 'search_executed': bool(search_executed), 'visit_executed': bool(visit_executed), 'tool_evidence_available': bool(evidence.strip()), 'evidence_chars': len(evidence)}


def _evidence_urls(evidence: str) -> set[str]:
    return {clean for u in _URL_RE.findall(evidence or '') if (clean := _clean_source_url(u))}

def _youtube_url(url: str) -> bool:
    try:
        host = (urllib.parse.urlparse(url).hostname or '').lower()
    except Exception:
        return False
    return host in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'}

def _model_tokens(model: str) -> List[str]:
    tokens = re.findall('[a-z0-9]+', _text(model).lower())
    stop = {'inc', 'ltd', 'corp', 'corporation', 'notebook', 'laptop', 'desktop', 'computer', 'pc', 'the', 'series'}
    return [t for t in tokens if len(t) >= 2 and t not in stop]

def _exact_model_match(model: str, title: str, evidence: str='') -> bool:
    tokens = _model_tokens(model)
    if not tokens:
        return False
    hay = (title + ' ' + evidence).lower()
    matched = sum((1 for t in tokens if t in hay))
    needed = max(1, int(len(tokens) * 0.7 + 0.999))
    distinctive = [t for t in tokens if any((c.isdigit() for c in t))]
    distinctive_ok = not distinctive or any((t in hay for t in distinctive))
    return matched >= needed and distinctive_ok

def _youtube_oembed(url: str, timeout: float=8.0) -> Optional[Dict[str, str]]:
    endpoint = 'https://www.youtube.com/oembed?' + urllib.parse.urlencode({'url': url, 'format': 'json'})
    req = urllib.request.Request(endpoint, headers={'User-Agent': 'CorePulse/0.9.18.14a'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if getattr(resp, 'status', 200) != 200:
                return None
            data = json.loads(resp.read().decode('utf-8', errors='replace'))
        title = _text(data.get('title'))
        author = _text(data.get('author_name'))
        return {'title': title, 'channel': author} if title else None
    except Exception:
        return None

def _tutorial_action_match(title: str, *, component_type: str='', problem_title: str='', tutorial_action: str='') -> bool:
    hay = _text(title).lower()
    ctype = _text(component_type).upper()
    combined = ' '.join((_text(problem_title), _text(tutorial_action))).lower()
    if ctype == 'CPU' or any(x in combined for x in ('tjmax', 'cpu', 'procesador')):
        terms = ('cooling', 'fan', 'heatsink', 'thermal', 'paste', 'repaste', 'disassembly', 'teardown', 'cleaning', 'ventilador', 'disipador', 'térmica', 'termica', 'pasta', 'desmontaje', 'limpieza')
    elif ctype == 'GPU' or 'hotspot' in combined:
        terms = ('gpu', 'cooling', 'fan', 'heatsink', 'thermal', 'pad', 'paste', 'disassembly', 'teardown', 'ventilador', 'disipador', 'desmontaje')
    elif ctype == 'RAM':
        terms = ('ram', 'memory', 'upgrade', 'slot', 'install', 'replacement', 'memoria', 'ampli', 'instal')
    elif ctype == 'STORAGE':
        terms = ('ssd', 'nvme', 'm.2', 'storage', 'drive', 'upgrade', 'replace', 'install', 'almacenamiento', 'unidad', 'instal')
    elif ctype == 'BATTERY':
        terms = ('battery', 'bater', 'replace', 'replacement', 'disassembly', 'desmontaje')
    else:
        tokens = [t for t in _model_tokens(tutorial_action) if len(t) >= 4]
        return bool(tokens and any(t in hay for t in tokens))
    return any(term in hay for term in terms)


def _verify_tutorial(candidate: Dict[str, Any], evidence: str, device_model: str, *, component_type: str='', problem_title: str='', tutorial_action: str='', oembed_func=None) -> Dict[str, Any]:
    url = _text(candidate.get('url'))
    if not url or not _youtube_url(url):
        return {'status': 'NOT_FOUND', 'reason': 'No se recibió una URL de YouTube válida.'}
    evidence_urls = _evidence_urls(evidence)
    if url not in evidence_urls and url not in evidence:
        return {'status': 'NOT_FOUND', 'reason': 'La URL no aparece en la evidencia de búsqueda de Groq.'}
    check = oembed_func or _youtube_oembed
    metadata = check(url)
    if not metadata:
        return {'status': 'NOT_FOUND', 'reason': 'YouTube no confirmó que el video sea público/accesible.'}
    title = _text(metadata.get('title'))
    # El modelo exacto debe aparecer en el título público confirmado por YouTube;
    # no basta con que aparezca en otra parte de la evidencia de búsqueda.
    if not _exact_model_match(device_model, title, ''):
        return {'status': 'NOT_FOUND', 'reason': 'El título público del video no coincide con el modelo exacto detectado.'}
    if not _tutorial_action_match(title, component_type=component_type, problem_title=problem_title, tutorial_action=tutorial_action):
        return {'status': 'NOT_FOUND', 'reason': 'El video coincide con el modelo, pero no con la acción requerida para el problema detectado.'}
    return {'status': 'VERIFIED_EXACT', 'title': title, 'url': url, 'channel': _text(metadata.get('channel'), 'N/A'), 'verification': 'Groq web-search evidence + YouTube oEmbed + exact-model title match + problem-action match'}

def _new_client(Groq, key: str, timeout: float):
    """Gestiona la operación `new_client` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    return Groq(api_key=key, timeout=timeout)

def _error_status_code(exc: Exception) -> Optional[int]:
    for value in (getattr(exc, 'status_code', None), getattr(getattr(exc, 'response', None), 'status_code', None)):
        try:
            if value is not None:
                return int(value)
        except Exception:
            pass
    match = re.search('\\b(?:Error code:|status(?:_code)?[=: ]+)\\s*(\\d{3})\\b', str(exc), re.I)
    return int(match.group(1)) if match else None

def _safe_error(exc: Exception) -> str:
    text = f'{type(exc).__name__}: {exc}'
    text = re.sub('(?i)(authorization\\s*[:=]\\s*bearer\\s+)[^\\s,}]+', '\\1[REDACTED]', text)
    text = re.sub('(?i)(gsk_[a-z0-9_-]{8,})', '[REDACTED]', text)
    return text[:900]

def _request_size_bytes(kwargs: Dict[str, Any]) -> int:
    try:
        return len(json.dumps(kwargs, ensure_ascii=False, separators=(',', ':'), default=str).encode('utf-8'))
    except Exception:
        return -1

def _research_models(available_models: Iterable[str]) -> List[str]:
    available = {str(x) for x in available_models if _text(x)}
    if not available:
        return list(RESEARCH_MODELS)
    return [m for m in RESEARCH_MODELS if m in available]


def research_device_support(*, api_key: str, available_models: Iterable[str], device: Dict[str, Any], problems: List[Dict[str, Any]]) -> Dict[str, Any]:
    enabled = _text(os.getenv('COREPULSE_AI_WEB_RESEARCH', '1')).lower() not in {'0', 'false', 'off', 'no'}
    if not enabled:
        return {'status': 'DISABLED', 'capability': 'DISABLED', 'model': None, 'tutorials': {}, 'upgradeability': {}, 'sources': [], 'search_executed': False, 'visit_executed': False, 'executed_tools_count': 0, 'tool_types': [], 'source_count': 0, 'reason': 'COREPULSE_AI_WEB_RESEARCH desactivado.'}
    available = set((str(x) for x in available_models))
    research_model = next((m for m in RESEARCH_MODELS if m in available), None) if available else RESEARCH_MODELS[0]
    if not api_key:
        return {'status': 'UNAVAILABLE', 'capability': 'UNAVAILABLE', 'model': research_model, 'tutorials': {}, 'upgradeability': {}, 'sources': [], 'search_executed': False, 'visit_executed': False, 'executed_tools_count': 0, 'tool_types': [], 'source_count': 0, 'reason': 'GROQ_API_KEY no configurada.'}
    if not research_model:
        return {'status': 'UNAVAILABLE', 'capability': 'UNAVAILABLE', 'model': None, 'tutorials': {}, 'upgradeability': {}, 'sources': [], 'search_executed': False, 'visit_executed': False, 'executed_tools_count': 0, 'tool_types': [], 'source_count': 0, 'reason': 'La cuenta/model discovery no expone groq/compound ni groq/compound-mini.'}
    form = _text(device.get('form_factor'), 'UNKNOWN').upper()
    model = _text(device.get('model'), 'N/A')
    manufacturer = _text(device.get('manufacturer'), 'N/A')
    motherboard = _text(device.get('motherboard'), 'N/A')
    target = device_support_target(device)
    problem_rows = []
    problem_by_id: Dict[str, Dict[str, Any]] = {}
    for p in problems:
        pid = _text(p.get('problem_id'))
        component_name = _text(p.get('component_name'), 'N/A')
        tutorial_action = _text(p.get('tutorial_action'), 'mantenimiento y solución de la condición detectada')
        search_query = ' '.join(x for x in (manufacturer, target, component_name if component_name != 'N/A' else '', tutorial_action) if x).strip()
        row = {'problem_id': pid, 'component_id': _text(p.get('component_id')), 'component_type': p.get('component_type'), 'component_name': component_name, 'title': p.get('title'), 'priority_level': p.get('priority_level'), 'priority_required': bool(p.get('priority_required')), 'tutorial_action': tutorial_action, 'search_query': search_query}
        problem_rows.append(row)
        if pid:
            problem_by_id[pid] = row
    prompt = f'''\nActúa como verificador web de mantenimiento de hardware para CorePulse.\nDebes USAR web_search. No uses visit_website en esta etapa.\n\nEquipo real detectado:\n- tipo: {form}\n- fabricante: {manufacturer}\n- modelo objetivo exacto: {target}\n- placa madre: {motherboard}\n\nProblemas confirmados/advisory de CorePulse (puede estar vacío si el equipo está sano):\n{json.dumps(problem_rows, ensure_ascii=False, separators=(',', ':'))}\n\nTareas:\n1) EJECUTA al menos una web_search para el modelo exacto "{target}". No respondas solo con conocimiento interno.\n2) Si existen problem_id, ejecuta búsquedas específicas usando el campo search_query de cada problema. Para cada uno busca UN tutorial de YouTube cuyo TÍTULO PÚBLICO indique claramente el MODELO EXACTO "{target}" y cuya temática coincida con tutorial_action. Si no existe uno exacto y verificable, tutorial=null. No uses tutoriales genéricos. Si no hay problemas, tutorials debe ser [].\n3) Para cada component_id presente en los problemas, investiga la reemplazabilidad/actualizabilidad física de ESE componente dentro de la plataforma exacta. No asumas nada por ser laptop o desktop. Usa VERIFIED_UPGRADEABLE solo con evidencia técnica que confirme modularidad/compatibilidad; VERIFIED_NOT_PRACTICAL solo con evidencia que confirme integración o no practicidad; en los demás casos usa UNVERIFIED.\n4) Las URL deben provenir de resultados reales de web_search. No inventes enlaces.\n\nDevuelve SOLO JSON:\n{{\n  "tutorials": [{{"problem_id":"...","url":"https://www.youtube.com/watch?v=..."}}],\n  "upgradeability": [{{"component_id":"CPU|GPU:0|STORAGE:0|...","component_type":"CPU|GPU|RAM|STORAGE","status":"VERIFIED_UPGRADEABLE|VERIFIED_NOT_PRACTICAL|UNVERIFIED","reason":"...","source_url":"https://... o null"}}]\n}}\n'''.strip()
    try:
        from groq import Groq
    except Exception as exc:
        return {'status': 'UNAVAILABLE', 'capability': 'UNAVAILABLE', 'model': research_model, 'target_model': target, 'tutorials': {}, 'upgradeability': {}, 'sources': [], 'search_executed': False, 'visit_executed': False, 'executed_tools_count': 0, 'tool_types': [], 'source_count': 0, 'reason': 'Groq SDK no disponible.', 'error': _safe_error(exc), 'attempts': []}
    search = _compound_web_search(Groq=Groq, api_key=api_key, available_models=available, prompt=prompt, timeout=50.0)
    message = search.pop('message', None)
    if message is None:
        return {'status': search.get('status', 'ERROR'), 'capability': search.get('capability', 'AVAILABLE'), 'model': search.get('model') or research_model, 'target_model': target, 'tutorials': {str(p.get('problem_id')): {'status': 'NOT_FOUND', 'reason': 'La verificación web no pudo completarse.'} for p in problems}, 'upgradeability': {}, 'sources': [], 'source_count': 0, 'reason': search.get('reason') or 'La llamada de investigación web falló.', 'error': search.get('error'), 'attempts': search.get('attempts') or [], 'request_mode': search.get('request_mode'), 'request_bytes': search.get('request_bytes'), 'search_executed': False, 'visit_executed': False, 'executed_tools_count': 0, 'tool_types': [], 'tool_evidence_available': False, 'evidence_chars': 0}
    content = getattr(message, 'content', '') or ''
    parsed = _extract_json(content) or {}
    trace = _tool_trace(message)
    evidence = _tool_evidence(message)
    evidence_urls = _evidence_urls(evidence)
    web_verified = bool(trace.get('search_executed') and trace.get('tool_evidence_available'))
    tutorials: Dict[str, Any] = {}
    tutorial_candidates = parsed.get('tutorials') if web_verified and isinstance(parsed.get('tutorials'), list) else []
    for candidate in tutorial_candidates:
        if not isinstance(candidate, dict):
            continue
        pid = _text(candidate.get('problem_id'))
        if not pid:
            continue
        problem = problem_by_id.get(pid) or {}
        tutorials[pid] = _verify_tutorial(
            candidate,
            evidence,
            target,
            component_type=_text(problem.get('component_type')),
            problem_title=_text(problem.get('title')),
            tutorial_action=_text(problem.get('tutorial_action')),
        )
    for p in problems:
        pid = _text(p.get('problem_id'))
        tutorials.setdefault(pid, {'status': 'NOT_FOUND', 'reason': f'No se encontró un tutorial exacto y verificable para {target}.'})
    upgrades: Dict[str, Any] = {}
    upgrades_by_component: Dict[str, Any] = {}
    valid_problem_components = {
        _text(row.get('component_id')): _text(row.get('component_type')).upper()
        for row in problem_rows if _text(row.get('component_id'))
    }
    upgrade_candidates = parsed.get('upgradeability') if web_verified and isinstance(parsed.get('upgradeability'), list) else []
    legacy_by_type: Dict[str, Any] = {}
    for item in upgrade_candidates:
        if not isinstance(item, dict):
            continue
        cid = _text(item.get('component_id'))
        ctype = _text(item.get('component_type')).upper()
        if ctype not in {'CPU', 'GPU', 'RAM', 'STORAGE'}:
            continue
        status = _text(item.get('status'), 'UNVERIFIED').upper()
        if status not in {'VERIFIED_UPGRADEABLE', 'VERIFIED_NOT_PRACTICAL', 'UNVERIFIED'}:
            status = 'UNVERIFIED'
        src = _clean_source_url(item.get('source_url'))
        if src and src not in evidence_urls and src not in evidence:
            src = ''
            status = 'UNVERIFIED'
        row = {'status': status, 'reason': _text(item.get('reason'), 'Actualización física no verificada.'), 'source_url': src or None}
        if cid and cid in valid_problem_components and valid_problem_components[cid] == ctype:
            upgrades_by_component[cid] = row
        elif not cid:
            legacy_by_type[ctype] = row

    for cid, ctype in valid_problem_components.items():
        if ctype not in {'CPU', 'GPU', 'RAM', 'STORAGE'}:
            continue
        upgrades_by_component.setdefault(cid, {
            'status': 'UNVERIFIED',
            'reason': 'La reemplazabilidad/compatibilidad física de este componente no fue verificada para la plataforma exacta.',
            'source_url': None,
        })

    for ctype in ('CPU', 'GPU', 'RAM', 'STORAGE'):
        type_rows = [value for cid, value in upgrades_by_component.items() if valid_problem_components.get(cid) == ctype]
        if type_rows:
            statuses = {_text(value.get('status'), 'UNVERIFIED').upper() for value in type_rows}
            if len(statuses) == 1:
                upgrades[ctype] = dict(type_rows[0])
            else:
                upgrades[ctype] = {
                    'status': 'UNVERIFIED',
                    'reason': 'La reemplazabilidad varía entre componentes del mismo tipo; use la decisión específica por component_id.',
                    'source_url': None,
                }
        elif ctype in legacy_by_type:
            upgrades[ctype] = legacy_by_type[ctype]
    sources = sorted(evidence_urls)[:20]
    if web_verified:
        status = 'OK'
        reason = 'Groq Compound ejecutó web_search y entregó evidencia de herramienta verificable.'
    elif search.get('status') == 'AVAILABLE_NOT_EXECUTED':
        status = 'AVAILABLE_NOT_EXECUTED'
        reason = search.get('reason') or 'Compound respondió sin búsqueda verificable.'
    else:
        status = search.get('status') or 'PARTIAL'
        reason = search.get('reason') or 'La investigación web no pudo verificarse completamente.'
    return {'status': status, 'capability': 'AVAILABLE', 'model': search.get('model') or research_model, 'target_model': target, 'tutorials': tutorials, 'upgradeability': upgrades, 'upgradeability_by_component': upgrades_by_component, 'sources': sources, 'source_count': len(sources), 'request_mode': search.get('request_mode'), 'request_bytes': search.get('request_bytes'), 'attempts': search.get('attempts') or [], 'reason': reason, **trace}
_RELEVANCE_CLASSES = {'OPTIMO', 'ESTANDAR', 'JUSTO', 'POR_DEBAJO_DEL_ESTANDAR', 'NO_EVALUABLE'}
_RELEVANCE_CONFIDENCE = {'ALTA', 'MEDIA', 'BAJA'}
_SOURCE_TIER_A = ('pcisig.com', 'jedec.org')
_SOURCE_TIER_B = ('notebookcheck.net', 'techpowerup.com', 'tomshardware.com', 'anandtech.com', 'pcmag.com', 'pcworld.com', 'computerbase.de', 'guru3d.com', 'cpubenchmark.net', 'passmark.com', 'cpu-monkey.com')
_REJECT_SOURCE_DOMAINS = ('ebay.com', 'amazon.com', 'amazon.co.uk', 'amazon.de', 'amazon.es', 'aliexpress.com', 'temu.com', 'walmart.com', 'mercadolibre.com', 'facebook.com', 'instagram.com', 'tiktok.com', 'pinterest.com', 'reddit.com', 'quora.com', 'edmunds.com')

def _relevance_fallback_rows(components: List[Dict[str, Any]], reason: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for comp in components:
        if not isinstance(comp, dict):
            continue
        cid = _text(comp.get('id') or comp.get('component_id'))
        if not cid:
            continue
        rows.append({'component_id': cid, 'component_type': _text(comp.get('type') or comp.get('component_type'), 'UNKNOWN').upper(), 'detected_hardware': _text(comp.get('name') or comp.get('detected_hardware'), 'N/A'), 'classification': 'NO_EVALUABLE', 'confidence': 'BAJA', 'reason': reason, 'sources': [], 'source_count': 0, 'research_status': 'NO_EVIDENCE'})
    return rows

def _component_exact_in_evidence(component_name: str, evidence: str) -> bool:
    """Gestiona la operación `component_exact_in_evidence` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    name = _text(component_name).split(' · ', 1)[0].strip()
    if not name:
        return False
    tokens = _model_tokens(name)
    if not tokens:
        return False
    hay = (evidence or '').lower()
    distinctive = [t for t in tokens if any((ch.isdigit() for ch in t))]
    if distinctive and (not any((t in hay for t in distinctive))):
        return False
    matched = sum((1 for t in tokens if t in hay))
    needed = max(1, int(len(tokens) * 0.6 + 0.999))
    return matched >= needed

def _component_identity_specific(comp: Dict[str, Any]) -> tuple[bool, str]:
    """Valida identidad mediante una política genérica basada en los datos detectados."""
    return _universal_identity_specific(
        _text(comp.get('component_type'), 'UNKNOWN'),
        _text(comp.get('detected_hardware'), 'N/A'),
        comp.get('facts') if isinstance(comp.get('facts'), dict) else {},
    )

def _search_result_items(message: Any) -> List[Dict[str, Any]]:
    """Gestiona la operación `search_result_items` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    out: List[Dict[str, Any]] = []
    seen = set()
    for tool in _tool_records(message):
        raw = tool.get('search_results')
        candidates: List[Any] = []
        if isinstance(raw, dict):
            vals = raw.get('results')
            if isinstance(vals, list):
                candidates.extend(vals)
        elif isinstance(raw, list):
            candidates.extend(raw)
        for item in candidates:
            if isinstance(item, dict):
                url = _clean_source_url(item.get('url') or item.get('link'))
                title = _text(item.get('title'))
                content = _text(item.get('content') or item.get('snippet') or item.get('text'))
                score = item.get('score')
            else:
                url, title, content, score = ('', '', _text(item), None)
            key = (url, title, content[:160])
            if key in seen:
                continue
            seen.add(key)
            out.append({'url': url, 'title': title, 'content': content, 'score': score})
    if out:
        return out
    evidence = _tool_evidence(message)
    for url in sorted(_evidence_urls(evidence)):
        out.append({'url': url, 'title': '', 'content': evidence[:3500], 'score': None})
    return out

def _host(url: str) -> str:
    try:
        return (urllib.parse.urlparse(url).hostname or '').lower().removeprefix('www.')
    except Exception:
        return ''

def _domain_matches(host: str, domains: Iterable[str]) -> bool:
    return any((host == d or host.endswith('.' + d) for d in domains))

def _result_blob(item: Dict[str, Any]) -> str:
    return ' '.join((_text(item.get('title')), _text(item.get('url')), _text(item.get('content')))).lower()


def _category_terms(ctype: str) -> tuple[str, ...]:
    return {'CPU': ('processor', 'cpu', 'core', 'thread', 'single-core', 'multi-core', 'benchmark'), 'GPU': ('gpu', 'graphics', 'video card', 'vram', 'benchmark', 'raster', 'ray tracing'), 'RAM': ('computer memory', 'system memory', 'ram memory', 'memory (ram', 'ddr4', 'ddr5', 'gb ram', 'windows pc', 'laptop', 'desktop'), 'STORAGE': ('ssd', 'nvme', 'storage', 'solid state', 'm.2', 'sata', 'pcie', 'drive')}.get(ctype, ())

def _context_terms(year: int) -> tuple[str, ...]:
    return (str(int(year)), 'current', 'mainstream', 'recommended', 'recommendation', 'modern', 'comparison', 'compare', 'versus', ' vs ', 'generation', 'today', 'standard', 'entry-level', 'mid-range', 'midrange', 'high-end', 'requirements')

def _ram_result_relevant(blob: str) -> bool:
    automotive = ('pickup', 'truck', 'towing', 'horsepower', 'engine', 'vehicle', 'ram 1500', 'ram 2500', 'ram 3500')
    if any((x in blob for x in automotive)):
        return False
    return any((x in blob for x in _category_terms('RAM')))

def _result_role(comp: Dict[str, Any], item: Dict[str, Any], year: int) -> str:
    """Gestiona la operación `result_role` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    quality = _source_quality(item, comp)
    if quality['tier'] == 'REJECTED':
        return 'irrelevant'
    try:
        score = item.get('score')
        if score is not None and float(score) < 0.15:
            return 'irrelevant'
    except Exception:
        pass
    ctype = _text(comp.get('component_type'), 'UNKNOWN').upper()
    blob = _result_blob(item)
    if ctype == 'RAM':
        if not _ram_result_relevant(blob):
            return 'irrelevant'
        facts = comp.get('facts') if isinstance(comp.get('facts'), dict) else {}
        total = facts.get('total_gb')
        capacity_hit = False
        try:
            nominal = int(round(float(total)))
            capacity_hit = bool(re.search(f'\\b{nominal}\\s*gb\\b', blob, re.I))
        except Exception:
            pass
        context_hit = any((t in blob for t in _context_terms(year)))
        if capacity_hit and context_hit:
            return 'both'
        if capacity_hit:
            return 'component'
        if context_hit:
            return 'context'
        return 'context'
    category_hit = any((t in blob for t in _category_terms(ctype)))
    if not category_hit:
        return 'irrelevant'
    exact_hit = _component_exact_in_evidence(comp.get('detected_hardware'), blob)
    context_hit = any((t in blob for t in _context_terms(year)))
    if exact_hit and context_hit:
        return 'both'
    if exact_hit:
        return 'component'
    if context_hit:
        return 'context'
    return 'irrelevant'

def _annotated_valid_results(comp: Dict[str, Any], message: Any, year: int, search_intent: str='auto') -> List[Dict[str, Any]]:
    """Valida resultados y conserva el propósito verificable de la consulta que los produjo.

    `search_intent` nunca convierte una fuente ajena en evidencia válida: la fuente debe seguir
    perteneciendo a la categoría correcta, no estar rechazada y, para intención `component`,
    debe contener la identidad exacta. La intención solo evita perder contexto válido porque el
    snippet no repita literalmente "current/mainstream/2026".
    """
    out: List[Dict[str, Any]] = []
    intent = _text(search_intent, 'auto').lower()
    ctype = _text(comp.get('component_type'), 'UNKNOWN').upper()
    for item in _search_result_items(message):
        quality = _source_quality(item, comp)
        if quality['tier'] == 'REJECTED':
            continue
        role = _result_role(comp, item, year)
        blob = _result_blob(item)
        category_ok = _ram_result_relevant(blob) if ctype == 'RAM' else any((t in blob for t in _category_terms(ctype)))
        exact_ok = True if ctype == 'RAM' else _component_exact_in_evidence(comp.get('detected_hardware'), blob)
        if role == 'irrelevant':
            if intent == 'component' and category_ok and exact_ok:
                role = 'component'
            elif intent == 'context' and category_ok:
                role = 'context'
            elif intent == 'comparison' and category_ok:
                role = 'both' if exact_ok else 'context'
        elif intent == 'context' and role == 'component' and category_ok:
            # La consulta fue explícitamente de contexto actual; conserva ambos roles.
            role = 'both'
        elif intent == 'comparison' and role in {'component', 'context'} and exact_ok and category_ok:
            role = 'both'
        if role == 'irrelevant':
            continue
        enriched = dict(item)
        enriched['role'] = role
        enriched['search_intent'] = intent
        enriched['quality_tier'] = quality['tier']
        enriched['quality_points'] = quality['points']
        enriched['host'] = quality['host']
        out.append(enriched)
    return out

def _merge_results_base(*groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    for group in groups:
        for item in group or []:
            url = _clean_source_url(item.get('url'))
            key = url or _text(item.get('title')) + '|' + _text(item.get('content'))[:160]
            if not key:
                continue
            current = by_key.get(key)
            if current is None or int(item.get('quality_points') or 0) > int(current.get('quality_points') or 0):
                by_key[key] = dict(item)
            elif current.get('role') != item.get('role') and {current.get('role'), item.get('role')} == {'component', 'context'}:
                current['role'] = 'both'
    return sorted(by_key.values(), key=lambda x: (int(x.get('quality_points') or 0), float(x.get('score') or 0.0)), reverse=True)[:10]


def _valid_component_results(comp: Dict[str, Any], message: Any, year: Optional[int]=None) -> List[Dict[str, Any]]:
    """Gestiona la operación `valid_component_results` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    return _annotated_valid_results(comp, message, int(year or 2026))[:8]

def _evidence_packet(results: List[Dict[str, Any]], max_chars: int=7500) -> str:
    chunks: List[str] = []
    used = 0
    for idx, item in enumerate(results[:8], 1):
        text = f"SOURCE {idx} [role={_text(item.get('role'), 'unknown')}; quality={_text(item.get('quality_tier'), 'C')}]\nTITLE: {_text(item.get('title'))}\nURL: {_clean_source_url(item.get('url'))}\nSNIPPET: {_text(item.get('content'))[:1200]}"
        if used + len(text) > max_chars:
            remain = max_chars - used
            if remain > 180:
                chunks.append(text[:remain])
            break
        chunks.append(text)
        used += len(text)
    return '\n\n'.join(chunks)

def _category_rubric(ctype: str) -> str:
    if ctype == 'CPU':
        return 'CPU: compara con el mainstream ACTUAL de la misma clase indicada por la evidencia, no solo con CPUs líderes. Considera rendimiento single/multi-core, núcleos/hilos y eficiencia solo cuando las fuentes lo respaldan. Un CPU antiguo no es automáticamente POR_DEBAJO si sigue satisfaciendo el uso mainstream.'
    if ctype == 'GPU':
        return 'GPU: compara con el mainstream ACTUAL de la misma categoría (integrada/dedicada y móvil/desktop solo si la evidencia lo confirma). Considera rendimiento relativo, VRAM y capacidades/API verificadas. No penalices únicamente por generación o fecha de lanzamiento.'
    if ctype == 'RAM':
        return 'RAM: la capacidad instalada real es el criterio principal; velocidad y módulos son secundarios y solo se usan si fueron detectados. Compara contra necesidades mainstream actuales de Windows/PC, no contra estaciones de trabajo o gaming extremo.'
    if ctype == 'STORAGE':
        return 'STORAGE: considera tipo de unidad, interfaz, capacidad y rendimiento verificable en conjunto. La existencia de PCIe Gen4/Gen5 NO convierte por sí sola un NVMe Gen3 funcional en POR_DEBAJO_DEL_ESTANDAR. Compara contra experiencia mainstream actual, no únicamente contra SSD high-end.'
    return 'Compara únicamente con el mainstream actual de la misma categoría.'

def _classification_prompt(comp: Dict[str, Any], year: int, results: List[Dict[str, Any]]) -> str:
    ctype = _text(comp.get('component_type'), 'UNKNOWN').upper()
    name = _text(comp.get('detected_hardware'), 'N/A')
    facts = comp.get('facts') if isinstance(comp.get('facts'), dict) else {}
    rubric = 'OPTIMO=claramente por encima del mainstream actual de su categoría; ESTANDAR=cumple bien las expectativas mainstream actuales sin una limitación material dominante; JUSTO=sigue siendo útil pero queda detrás del mainstream en uno o más aspectos relevantes; POR_DEBAJO_DEL_ESTANDAR=tiene limitaciones materiales que lo dejan claramente por debajo del mainstream de su categoría; NO_EVALUABLE=la evidencia no permite una conclusión defendible.'
    return f"CorePulse clasifica la VIGENCIA TECNOLOGICA {year} de UN componente universal.\nTipo={ctype}; hardware detectado={name}; facts reales={json.dumps(facts, ensure_ascii=False, separators=(',', ':'))}.\nRubrica global: {rubric}\nRubrica de categoría: {_category_rubric(ctype)}\nReglas obligatorias: salud, temperatura y SMART NO son vigencia; no inventes especificaciones; no uses conocimiento externo a SOURCE; no compares solo contra high-end; no cites URLs en reason. Cada afirmación técnica de reason debe estar apoyada por SOURCE o facts. Si falta evidencia de comparación mainstream, usa NO_EVALUABLE/BAJA.\n\n" + _evidence_packet(results) + '\n\nDevuelve SOLO JSON: {"classification":"ESTANDAR","confidence":"MEDIA","reason":"1-3 frases claras"}'



def _non_relevance_row(comp: Dict[str, Any], year: int) -> Dict[str, Any]:
    ctype = _text(comp.get('component_type'), 'UNKNOWN').upper()
    name = _text(comp.get('detected_hardware'), 'N/A')
    if ctype == 'BATTERY':
        reason = f'CorePulse no clasifica la vigencia tecnológica de la batería para {int(year)} como si fuera CPU/GPU/RAM/almacenamiento. La batería se evalúa por capacidad, degradación y estado técnico real en su sección correspondiente.'
    else:
        reason = f'No existe un criterio universal de vigencia {int(year)} definido para el tipo {ctype}; CorePulse evita inventar una clasificación.'
    return {'component_id': comp.get('component_id'), 'component_type': ctype, 'detected_hardware': name, 'classification': 'NO_EVALUABLE', 'confidence': 'BAJA', 'reason': reason, 'sources': [], 'source_count': 0, 'research_status': 'NOT_APPLICABLE'}

_REJECTED_SOURCE_DOMAINS = ('exa.ai', 'gpu101.com', 'nvidiareview.com', 'bestproducts.com', 'bestreviews.com')
_TRACKING_QUERY_KEYS = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'fbclid', 'ref', 'ref_', 'tag', 'source'}
_POSITION_VALUES = ('WELL_ABOVE', 'ABOVE', 'MEETS', 'SLIGHTLY_BELOW', 'FAR_BELOW', 'UNKNOWN')
_POSITION_SCORE = {'WELL_ABOVE': 2.0, 'ABOVE': 1.0, 'MEETS': 0.0, 'SLIGHTLY_BELOW': -1.0, 'FAR_BELOW': -2.0, 'UNKNOWN': None}
_CATEGORY_WEIGHTS = {'CPU': (0.62, 0.23, 0.15), 'GPU': (0.62, 0.23, 0.15), 'RAM': (0.72, 0.18, 0.1), 'STORAGE': (0.58, 0.24, 0.18)}
_DECISION_METHOD_INITIAL = 'COREPULSE_DETERMINISTIC_RUBRIC_V1'

def _clean_source_url(value: Any) -> str:
    """Gestiona la operación `clean_source_url` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    raw = _text(value).strip()
    if not raw:
        return ''
    raw = raw.split('\\n', 1)[0].split('\n', 1)[0].strip()
    raw = re.sub('(?:\\\\?n)?L\\d+:.*$', '', raw, flags=re.I).strip()
    match = re.search('https?://[^\\s<>{}\\[\\]\\"\']+', raw, flags=re.I)
    if match:
        raw = match.group(0)
    raw = raw.rstrip(' \t\r\n.,;:!?)]}>|\'"\\')
    try:
        parsed = urllib.parse.urlsplit(raw)
    except Exception:
        return ''
    if parsed.scheme.lower() not in {'http', 'https'} or not parsed.hostname:
        return ''
    host = parsed.hostname.lower()
    try:
        q = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        q = [(k, v) for k, v in q if k.lower() not in _TRACKING_QUERY_KEYS and (not k.lower().startswith('utm_'))]
        query = urllib.parse.urlencode(q, doseq=True)
    except Exception:
        query = parsed.query
    netloc = host
    if parsed.port:
        netloc = f'{host}:{parsed.port}'
    path = parsed.path or '/'
    cleaned = urllib.parse.urlunsplit((parsed.scheme.lower(), netloc, path, query, ''))
    return cleaned.rstrip('/') if path != '/' else cleaned

def _source_quality(item: Dict[str, Any], comp: Optional[Dict[str, Any]]=None) -> Dict[str, Any]:
    """Gestiona la operación `source_quality` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    url = _clean_source_url(item.get('url'))
    host = _host(url)
    blob = _result_blob(item)
    try:
        parsed = urllib.parse.urlparse(url)
        path = (parsed.path or '').lower()
    except Exception:
        path = ''
    reject = not url or _domain_matches(host, tuple(NOISY_SEARCH_DOMAINS) + _REJECT_SOURCE_DOMAINS + _REJECTED_SOURCE_DOMAINS) or 'product-similar-image' in path or (host in {'google.com', 'bing.com', 'search.yahoo.com', 'duckduckgo.com'} and '/search' in path) or any((x in blob for x in ('sponsored listing', 'buy it now', 'add to cart', 'auction listing', "best review don't buy", 'coupon code', 'price comparison')))
    if reject:
        return {'tier': 'REJECTED', 'points': 0, 'host': host}
    if _domain_matches(host, _SOURCE_TIER_A) or (isinstance(comp, dict) and host_looks_official(host, comp)):
        return {'tier': 'A', 'points': 3, 'host': host}
    if _domain_matches(host, _SOURCE_TIER_B):
        return {'tier': 'B', 'points': 2, 'host': host}
    return {'tier': 'C', 'points': 1, 'host': host}

def _evidence_profile(comp: Dict[str, Any], results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Resume evidencia por componente sin exigir que una misma fuente haga dos trabajos distintos.

    la capa por componente separa evidencia de identidad/especificación y evidencia de contexto mainstream.
    Una clasificación solo es posible cuando existen fuentes independientes y suficiente calidad,
    pero no exige que el snippet repita literalmente palabras como "mainstream" si la consulta
    que produjo la fuente ya estaba dedicada a ese contexto.
    """
    component_count = sum((1 for x in results if x.get('role') in {'component', 'both'}))
    context_count = sum((1 for x in results if x.get('role') in {'context', 'both'}))
    tier_counts = {tier: sum((1 for x in results if x.get('quality_tier') == tier)) for tier in ('A', 'B', 'C')}
    quality_points = sum((int(x.get('quality_points') or 0) for x in results))
    strong_hosts = {_text(x.get('host')) for x in results if x.get('quality_tier') in {'A', 'B'} and _text(x.get('host'))}
    independent_hosts = {_text(x.get('host')) for x in results if _text(x.get('host'))}
    ctype = _text(comp.get('component_type'), 'UNKNOWN').upper()
    if ctype == 'RAM':
        # Para RAM la capacidad real detectada es la identidad; la web aporta el contexto actual.
        base_sufficient = context_count >= 2 and len(independent_hosts) >= 2 and quality_points >= 3
    else:
        base_sufficient = component_count >= 1 and context_count >= 1 and len(independent_hosts) >= 2 and quality_points >= 3
    quality_ready = len(strong_hosts) >= 1 and len(independent_hosts) >= 2
    return {
        'sufficient': bool(base_sufficient and quality_ready),
        'base_sufficient': bool(base_sufficient),
        'quality_ready': bool(quality_ready),
        'component_sources': component_count,
        'context_sources': context_count,
        'quality_points': quality_points,
        'tier_counts': tier_counts,
        'strong_hosts': len(strong_hosts),
        'independent_hosts': len(independent_hosts),
        'source_count': len(results),
    }

def _axis_definitions(ctype: str) -> str:
    return {'CPU': 'primary_position=posición de rendimiento CPU frente al mainstream ACTUAL de la misma clase; secondary_position=adecuación de núcleos/hilos y rendimiento multihilo; tertiary_position=eficiencia/capacidades modernas solo si las fuentes lo permiten.', 'GPU': 'primary_position=posición de rendimiento gráfico práctico frente al mainstream ACTUAL de la misma categoría; secondary_position=adecuación de VRAM/capacidad de memoria; tertiary_position=capacidades/API/features modernas verificadas.', 'RAM': 'primary_position=adecuación de capacidad instalada frente a necesidades mainstream ACTUALES; secondary_position=velocidad/configuración solo si fueron realmente detectadas y contextualizadas; tertiary_position=margen razonable para cargas mainstream.', 'STORAGE': 'primary_position=posición de interfaz/rendimiento práctico frente al storage mainstream ACTUAL; secondary_position=adecuación de capacidad; tertiary_position=experiencia práctica/tecnología de la unidad sin comparar solo contra high-end.'}.get(ctype, 'primary_position=posición frente al mainstream actual; secondary_position y tertiary_position=criterios secundarios verificables.')




def _confidence_assessment_base(profile: Dict[str, Any], axes: Dict[str, Any], classification: str, component_type: str='') -> Dict[str, Any]:
    """Calcula confianza por calidad/diversidad de evidencia, no por cantidad bruta.

    la rúbrica de confianza reserva ALTA para evidencia fuerte: cobertura suficiente, al menos tres hosts
    independientes, dos hosts fuertes, dos ejes comparativos conocidos, sin conflicto y
    con anclaje en fuentes Tier A o varias Tier B. La RAM usa su capacidad detectada como
    identidad local, pero mantiene las mismas exigencias de diversidad y ejes para ALTA.
    """
    cls = _text(classification, 'NO_EVALUABLE').upper()
    if cls == 'NO_EVALUABLE':
        return {'confidence': 'BAJA', 'score': 0, 'basis': 'Componente no evaluable.'}

    tiers = profile.get('tier_counts') if isinstance(profile.get('tier_counts'), dict) else {}
    a_count = int(tiers.get('A') or 0)
    b_count = int(tiers.get('B') or 0)
    source_count = int(profile.get('source_count') or 0)
    strong_hosts = int(profile.get('strong_hosts') or 0)
    independent_hosts = int(profile.get('independent_hosts') or 0)
    quality_points = int(profile.get('quality_points') or 0)
    component_sources = int(profile.get('component_sources') or 0)
    context_sources = int(profile.get('context_sources') or 0)
    ctype = _text(component_type, 'UNKNOWN').upper()
    known_axes = sum(1 for k in ('primary_position', 'secondary_position', 'tertiary_position') if _text(axes.get(k), 'UNKNOWN').upper() != 'UNKNOWN')
    conflict = bool(axes.get('evidence_conflict'))

    score = 0
    if source_count >= 8:
        score += 2
    elif source_count >= 5:
        score += 1
    if independent_hosts >= 5:
        score += 2
    elif independent_hosts >= 3:
        score += 1
    if strong_hosts >= 3:
        score += 2
    elif strong_hosts >= 2:
        score += 1
    if a_count >= 2:
        score += 2
    elif a_count >= 1:
        score += 1
    elif b_count >= 3:
        score += 1
    if quality_points >= 14:
        score += 2
    elif quality_points >= 8:
        score += 1
    if known_axes >= 3:
        score += 2
    elif known_axes >= 2:
        score += 1

    if ctype == 'RAM':
        coverage_ready = context_sources >= 3
    else:
        coverage_ready = component_sources >= 1 and context_sources >= 2
    if coverage_ready:
        score += 1

    high_gate = (
        bool(profile.get('sufficient'))
        and not conflict
        and source_count >= 6
        and independent_hosts >= 3
        and strong_hosts >= 2
        and known_axes >= 2
        and coverage_ready
        and (a_count >= 1 or b_count >= 3)
        and quality_points >= 8
    )

    if high_gate and score >= 8:
        conf = 'ALTA'
    elif (not conflict) and bool(profile.get('sufficient')) and score >= 4 and known_axes >= 1:
        conf = 'MEDIA'
    else:
        conf = 'BAJA'

    basis = (
        f'fuentes={source_count}; hosts={independent_hosts}; hosts_fuertes={strong_hosts}; '
        f'tierA={a_count}; tierB={b_count}; ejes={known_axes}; calidad={quality_points}; '
        f'cobertura={"OK" if coverage_ready else "PARCIAL"}; conflicto={"SI" if conflict else "NO"}'
    )
    return {'confidence': conf, 'score': int(score), 'basis': basis}


def _deterministic_confidence(profile: Dict[str, Any], axes: Dict[str, Any], classification: str, component_type: str='') -> str:
    return _confidence_assessment(profile, axes, classification, component_type).get('confidence', 'BAJA')

def _sanitize_reason(value: Any) -> str:
    reason = _text(value)
    if not reason:
        return ''
    reason = _URL_RE.sub('', reason)
    reason = re.sub('(?i)\\b(?:source|fuente)\\s*:\\s*', '', reason)
    reason = re.sub('\\s+', ' ', reason).strip(' -:;,.')
    return reason[:1200]

def _fallback_reason(comp: Dict[str, Any], year: int, classification: str, axes: Dict[str, Any]) -> str:
    name = _text(comp.get('detected_hardware'), 'El componente')
    primary = _text(axes.get('primary_position'), 'UNKNOWN').upper()
    position_es = {'WELL_ABOVE': 'claramente por encima', 'ABOVE': 'por encima', 'MEETS': 'en línea', 'SLIGHTLY_BELOW': 'algo por debajo', 'FAR_BELOW': 'claramente por debajo', 'UNKNOWN': 'sin evidencia suficiente'}.get(primary, 'sin evidencia suficiente')
    if classification == 'NO_EVALUABLE':
        return f'No existe evidencia comparativa suficiente para clasificar la vigencia {int(year)} de {name}.'
    return f"{name} se clasifica como {classification.replace('_', ' ')} para {int(year)} porque la evidencia verificada sitúa su criterio principal {position_es} del mainstream actual de su categoría."

def _reason_prompt(comp: Dict[str, Any], year: int, classification: str, score: Optional[float], axes: Dict[str, Any], results: List[Dict[str, Any]]) -> str:
    return f"CorePulse YA determinó de forma determinista la vigencia {int(year)}: {classification}. NO cambies esa clase. Tipo={_text(comp.get('component_type'), 'UNKNOWN')}; hardware={_text(comp.get('detected_hardware'), 'N/A')}; score={score}; ejes={json.dumps(axes, ensure_ascii=False, separators=(',', ':'))}.\nRedacta 1-3 frases claras explicando SOLO con facts/evidencia SOURCE por qué la clase fijada es defendible. No incluyas URLs, no inventes benchmarks ni especificaciones.\n\n" + _evidence_packet(results, max_chars=6000) + '\n\nDevuelve SOLO JSON {"reason":"..."}.'

def _generate_fixed_reason(*, Groq, api_key: str, available_models: Iterable[str], comp: Dict[str, Any], year: int, classification: str, score: Optional[float], axes: Dict[str, Any], results: List[Dict[str, Any]], timeout: float=30.0) -> Dict[str, Any]:
    available = {str(x) for x in available_models if _text(x)}
    candidates = [m for m in BROWSER_RESEARCH_MODELS if not available or m in available] or ['openai/gpt-oss-120b']
    schema = {'type': 'object', 'properties': {'reason': {'type': 'string'}}, 'required': ['reason'], 'additionalProperties': False}
    try:
        client = _new_client(Groq, api_key, timeout)
    except Exception:
        return {'status': 'FALLBACK', 'model': None, 'reason': _fallback_reason(comp, year, classification, axes)}
    for model_id in candidates:
        try:
            response = client.chat.completions.create(model=model_id, messages=[{'role': 'user', 'content': _reason_prompt(comp, year, classification, score, axes, results)}], max_completion_tokens=500, temperature=0, reasoning_effort='low', include_reasoning=False, response_format={'type': 'json_schema', 'json_schema': {'name': 'corepulse_relevance_reason', 'strict': True, 'schema': schema}})
            message = response.choices[0].message if response and response.choices else None
            parsed = _extract_json(getattr(message, 'content', '') if message is not None else '') or {}
            reason = _sanitize_reason(parsed.get('reason'))
            if reason:
                return {'status': 'OK', 'model': model_id, 'reason': reason}
        except Exception:
            continue
    return {'status': 'FALLBACK', 'model': None, 'reason': _fallback_reason(comp, year, classification, axes)}


def _confidence_ceiling(confidence: str, results: List[Dict[str, Any]]) -> str:
    conf = confidence if confidence in _RELEVANCE_CONFIDENCE else 'BAJA'
    tiers = {tier: sum((1 for x in results if x.get('quality_tier') == tier)) for tier in ('A', 'B', 'C')}
    strong_hosts = {_text(x.get('host')) for x in results if x.get('quality_tier') in {'A', 'B'} and _text(x.get('host'))}
    if not strong_hosts:
        return 'BAJA'
    if conf == 'ALTA' and (tiers['A'] < 1 or len(strong_hosts) < 2):
        return 'MEDIA'
    return conf


def _attempt_summary(attempts: Iterable[Dict[str, Any]]) -> str:
    bits: List[str] = []
    for attempt in attempts or []:
        if not isinstance(attempt, dict):
            continue
        model = _text(attempt.get('model'), 'N/A')
        mode = _text(attempt.get('mode'), 'N/A')
        status = _text(attempt.get('status'), 'N/A')
        http = attempt.get('http_status')
        bits.append(f'{model}/{mode}={status}' + (f' HTTP {http}' if http else ''))
    return '; '.join(bits[-4:]) or 'sin detalle de proveedor'

__all__ = ['research_device_support', 'research_hardware_relevance', '_verify_tutorial', '_tutorial_action_match', '_exact_model_match', '_compound_web_search', '_component_identity_specific', '_valid_component_results', '_classify_from_verified_evidence', '_deterministic_relevance_decision', '_deterministic_confidence', '_confidence_assessment', '_evidence_profile', '_source_quality', '_clean_source_url', '_component_search_prompts', '_component_search_strategies', '_annotated_valid_results', '_error_status_code', 'VERSION']
import time as _time
import threading as _threading
_DECISION_METHOD_RATE_AWARE = 'COREPULSE_DETERMINISTIC_RUBRIC_V2_RATE_AWARE'
_ROUTE_LOCK = _threading.RLock()
_ROUTE_STATE: Dict[str, Any] = {'preferred': None, 'disabled': set(), 'blocked_until': 0.0, 'last_call_at': 0.0, 'cache': {}}

def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except Exception:
        value = default
    return max(minimum, min(maximum, value))

def _retry_after_provider_base(exc: Exception) -> float:
    """Gestiona la operación `retry_after_provider` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    response = getattr(exc, 'response', None)
    headers = getattr(response, 'headers', None)
    if headers:
        for key in ('retry-after', 'Retry-After', 'x-ratelimit-reset-requests', 'x-ratelimit-reset-tokens'):
            try:
                raw = headers.get(key)
            except Exception:
                raw = None
            if raw is None:
                continue
            text = str(raw).strip()
            try:
                return max(0.0, float(text))
            except Exception:
                m = re.search('([0-9]+(?:\\.[0-9]+)?)\\s*s', text, re.I)
                if m:
                    return max(0.0, float(m.group(1)))
    text = str(exc)
    for pat in ('retry[^0-9]{0,20}([0-9]+(?:\\.[0-9]+)?)\\s*s', 'try again in\\s*([0-9]+(?:\\.[0-9]+)?)'):
        m = re.search(pat, text, re.I)
        if m:
            try:
                return max(0.0, float(m.group(1)))
            except Exception:
                pass
    return 0.0

def _pace_provider() -> None:
    """Gestiona la operación `pace_provider` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    min_interval = _env_float('COREPULSE_AI_MIN_CALL_INTERVAL_SECONDS', 1.75, 0.0, 10.0)
    while True:
        with _ROUTE_LOCK:
            now = _time.monotonic()
            blocked = float(_ROUTE_STATE.get('blocked_until') or 0.0)
            last = float(_ROUTE_STATE.get('last_call_at') or 0.0)
            wait = max(blocked - now, last + min_interval - now, 0.0)
            if wait <= 0:
                _ROUTE_STATE['last_call_at'] = now
                return
        _time.sleep(min(wait, 1.0))

def _mark_rate_limited(exc: Exception) -> float:
    retry = _retry_after_provider(exc)
    cooldown = retry if retry > 0 else _env_float('COREPULSE_AI_429_COOLDOWN_SECONDS', 12.0, 2.0, 60.0)
    with _ROUTE_LOCK:
        _ROUTE_STATE['blocked_until'] = max(float(_ROUTE_STATE.get('blocked_until') or 0.0), _time.monotonic() + cooldown)
    return cooldown

def _route_key(model: str, mode: str) -> str:
    return f'{model}|{mode}'

def _route_candidates(available_models: Iterable[str]) -> List[tuple[str, str]]:
    available = {str(x) for x in available_models if _text(x)}
    base: List[tuple[str, str]] = []
    for model in ('groq/compound-mini', 'groq/compound'):
        if not available or model in available:
            base.append((model, 'web_search_only'))
    for model in BROWSER_RESEARCH_MODELS:
        if not available or model in available:
            base.append((model, 'browser_search'))
    with _ROUTE_LOCK:
        preferred = _ROUTE_STATE.get('preferred')
        disabled = set(_ROUTE_STATE.get('disabled') or set())
    filtered = [x for x in base if _route_key(*x) not in disabled]
    if preferred and preferred in filtered:
        filtered.remove(preferred)
        filtered.insert(0, preferred)
    return filtered




def _component_search_prompts(comp: Dict[str, Any], year: int) -> List[str]:
    """Compatibilidad con pruebas/herramientas existentes."""
    return [x['prompt'] for x in _component_search_strategies(comp, year)]

def _ram_local_axes(comp: Dict[str, Any], results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Gestiona la operación `ram_local_axes` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    facts = comp.get('facts') if isinstance(comp.get('facts'), dict) else {}
    try:
        installed = float(facts.get('total_gb'))
    except Exception:
        return None
    if installed <= 0:
        return None
    refs: List[float] = []
    signal = re.compile('(?:standard|recommended|recommend|baseline|minimum|mainstream|est[aá]ndar|recomendad|minim|base)', re.I)
    gb = re.compile('\\b(4|8|12|16|24|32|48|64|96|128)\\s*gb\\b', re.I)
    for item in results:
        text = f"{_text(item.get('title'))}. {_text(item.get('content'))}"
        for sent in re.split('(?<=[.!?])\\s+|\\n+', text):
            if signal.search(sent):
                refs.extend((float(m.group(1)) for m in gb.finditer(sent)))
    if not refs:
        return None
    refs.sort()
    baseline = refs[len(refs) // 2]
    ratio = installed / baseline if baseline > 0 else 0
    if ratio >= 1.75:
        primary = 'ABOVE'
    elif ratio >= 0.9:
        primary = 'MEETS'
    elif ratio >= 0.6:
        primary = 'SLIGHTLY_BELOW'
    else:
        primary = 'FAR_BELOW'
    speeds = facts.get('configured_speeds_mhz') if isinstance(facts.get('configured_speeds_mhz'), list) else []
    secondary = 'MEETS' if speeds else 'UNKNOWN'
    return {'primary_position': primary, 'secondary_position': secondary, 'tertiary_position': 'UNKNOWN', 'material_limitation': 'YES' if primary == 'FAR_BELOW' else 'NO', 'evidence_conflict': False, 'basis': f'Referencia de capacidad inferida de evidencia web: ~{baseline:g} GB; instalado={installed:g} GB.'}

def _simple_local_axes(comp: Dict[str, Any], results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Gestiona la operación `simple_local_axes` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    ctype = _text(comp.get('component_type'), 'UNKNOWN').upper()
    if ctype == 'RAM':
        return _ram_local_axes(comp, results)
    name = _text(comp.get('detected_hardware'), '').split(' · ', 1)[0].lower()
    if not name:
        return None
    positive = negative = far_negative = 0
    context_seen = False
    for item in results:
        blob = _result_blob(item)
        if item.get('role') in {'context', 'both'}:
            context_seen = True
        if not _component_exact_in_evidence(name, blob):
            continue
        positive += sum((1 for p in ('competitive', 'still viable', 'meets', 'mainstream', 'similar performance', 'comparable') if p in blob))
        negative += sum((1 for p in ('slower than', 'behind', 'below mainstream', 'outperformed', 'lags behind', 'limited') if p in blob))
        far_negative += sum((1 for p in ('far behind', 'significantly slower', 'well below', 'obsolete', 'not recommended') if p in blob))
    if not context_seen or positive + negative + far_negative == 0:
        if ctype == 'STORAGE':
            text = ' '.join((_result_blob(x) for x in results))
            exact = ' '.join((_result_blob(x) for x in results if _component_exact_in_evidence(name, _result_blob(x))))
            if exact and ('nvme' in exact or 'ssd' in exact) and any((x in text for x in ('mainstream', 'current', 'standard'))):
                if not any((x in exact for x in ('hdd', 'hard disk', 'very slow', 'obsolete'))):
                    return {'primary_position': 'MEETS', 'secondary_position': 'UNKNOWN', 'tertiary_position': 'UNKNOWN', 'material_limitation': 'NO', 'evidence_conflict': False, 'basis': 'La evidencia identifica la unidad como SSD/NVMe y la contextualiza frente al almacenamiento actual sin una limitación material explícita.'}
        return None
    if far_negative >= 2 or (far_negative >= 1 and negative >= 2):
        primary = 'FAR_BELOW'
    elif negative > positive + 1:
        primary = 'SLIGHTLY_BELOW'
    elif positive > negative:
        primary = 'MEETS'
    else:
        return None
    return {'primary_position': primary, 'secondary_position': 'UNKNOWN', 'tertiary_position': 'UNKNOWN', 'material_limitation': 'YES' if primary == 'FAR_BELOW' else 'NO', 'evidence_conflict': bool(positive and negative), 'basis': 'Fallback léxico conservador aplicado únicamente sobre evidencia web verificada.'}




def _research_hardware_relevance_live(*, api_key: str, available_models: Iterable[str], components: List[Dict[str, Any]], year: int, progress_callback=None) -> Dict[str, Any]:
    """Investiga la operación `research_hardware_relevance` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    enabled = _text(os.getenv('COREPULSE_AI_WEB_RESEARCH', '1')).lower() not in {'0', 'false', 'off', 'no'}
    clean: List[Dict[str, Any]] = []
    for comp in components if isinstance(components, list) else []:
        if not isinstance(comp, dict):
            continue
        cid = _text(comp.get('id') or comp.get('component_id'))
        if not cid:
            continue
        facts = comp.get('facts') if isinstance(comp.get('facts'), dict) else {}
        clean.append({'component_id': cid, 'component_type': _text(comp.get('type') or comp.get('component_type'), 'UNKNOWN').upper(), 'detected_hardware': _text(comp.get('name') or comp.get('detected_hardware'), 'N/A'), 'facts': {k: v for k, v in facts.items() if v not in (None, '', [], {})}})
    if not clean:
        return {'status': 'OK', 'capability': 'AVAILABLE', 'model': None, 'models_used': [], 'hardware_relevance': [], 'sources': [], 'source_count': 0, 'search_executed': False, 'reason': 'No había componentes detectados para evaluar.', 'attempts': [], 'component_research': []}
    domain = {'CPU', 'GPU', 'RAM', 'STORAGE'}
    domain_components = [c for c in clean if c['component_type'] in domain]
    if not enabled:
        reason = 'La investigación web de vigencia está desactivada; CorePulse no inventa clasificaciones actuales.'
        return {'status': 'DISABLED', 'capability': 'DISABLED', 'model': None, 'models_used': [], 'hardware_relevance': _relevance_fallback_rows(clean, reason), 'sources': [], 'source_count': 0, 'search_executed': False, 'reason': reason, 'attempts': [], 'component_research': [], 'researchable_count': len(domain_components), 'evaluable_count': 0}
    if not api_key:
        reason = 'GROQ_API_KEY no configurada; no fue posible verificar criterios tecnológicos actuales.'
        return {'status': 'UNAVAILABLE', 'capability': 'UNAVAILABLE', 'model': None, 'models_used': [], 'hardware_relevance': _relevance_fallback_rows(clean, reason), 'sources': [], 'source_count': 0, 'search_executed': False, 'reason': reason, 'attempts': [], 'component_research': [], 'researchable_count': len(domain_components), 'evaluable_count': 0}
    try:
        from groq import Groq
    except Exception as exc:
        reason = 'Groq SDK no disponible.'
        return {'status': 'UNAVAILABLE', 'capability': 'UNAVAILABLE', 'model': None, 'models_used': [], 'hardware_relevance': _relevance_fallback_rows(clean, reason), 'sources': [], 'source_count': 0, 'search_executed': False, 'reason': reason, 'error': _safe_error(exc), 'attempts': [], 'component_research': [], 'researchable_count': len(domain_components), 'evaluable_count': 0}

    def emit(line: str) -> None:
        if callable(progress_callback):
            try:
                progress_callback(str(line))
            except Exception:
                pass
    rows_by_id: Dict[str, Dict[str, Any]] = {}
    all_sources: List[str] = []
    all_attempts: List[Dict[str, Any]] = []
    used_models: List[str] = []
    classifier_models: List[str] = []
    component_trace: List[Dict[str, Any]] = []
    any_search = False
    rate_limited = False
    evaluable = 0
    actually_researched = 0
    search_rounds_total = 0
    max_web_calls = int(_env_float('COREPULSE_AI_MAX_WEB_SEARCH_CALLS', 12, 1, 18))
    web_calls = 0
    researchable_order = [c for c in clean if c['component_type'] in domain]
    research_index = {c['component_id']: i + 1 for i, c in enumerate(researchable_order)}
    for comp in clean:
        cid, ctype = (comp['component_id'], comp['component_type'])
        if ctype not in domain:
            rows_by_id[cid] = _non_relevance_row(comp, year)
            continue
        idx = research_index[cid]
        identity_ok, identity_reason = _component_identity_specific(comp)
        if not identity_ok:
            rows_by_id[cid] = {'component_id': cid, 'component_type': ctype, 'detected_hardware': comp['detected_hardware'], 'classification': 'NO_EVALUABLE', 'confidence': 'BAJA', 'reason': identity_reason or f"Windows reportó una identidad genérica ({comp['detected_hardware']}) sin un modelo exacto verificable. CorePulse no infiere el modelo a partir de otro componente.", 'sources': [], 'source_count': 0, 'research_status': 'IDENTITY_INSUFFICIENT'}
            emit(f'[{idx}/{len(researchable_order)}] {ctype} · identidad insuficiente → NO EVALUABLE')
            continue
        actually_researched += 1
        emit(f"[{idx}/{len(researchable_order)}] {ctype} · {comp['detected_hardware']} · buscando evidencia")
        accumulated: List[Dict[str, Any]] = []
        component_models: List[str] = []
        rounds: List[Dict[str, Any]] = []
        strategies = _component_search_strategies(comp, year)
        search_status = 'NOT_RUN'
        for round_index, strategy in enumerate(strategies, 1):
            prompt = strategy['prompt']
            search_intent = strategy['intent']
            # Reserva al menos una llamada para cada componente clasificable que aún no pasó.
            # Así un componente difícil no puede consumir toda la cuota del informe.
            remaining_components = max(0, len(researchable_order) - idx)
            remaining_budget = max_web_calls - web_calls
            if web_calls >= max_web_calls or remaining_budget <= remaining_components:
                search_status = 'SEARCH_BUDGET_RESERVED'
                emit(f'    ronda {round_index} ({search_intent}): omitida · cuota reservada para {remaining_components} componente(s) restante(s) · {web_calls}/{max_web_calls}')
                break
            with _ROUTE_LOCK:
                blocked_for = max(0.0, float(_ROUTE_STATE.get('blocked_until') or 0.0) - _time.monotonic())
            if blocked_for > 0 and (not accumulated):
                search_status = 'RATE_LIMITED'
                rate_limited = True
                emit(f'    ronda {round_index} ({search_intent}): RATE_LIMITED · cooldown activo ~{blocked_for:.1f}s; no se fuerzan más llamadas')
                break
            search = _compound_web_search(Groq=Groq, api_key=api_key, available_models=available_models, prompt=prompt, timeout=38.0)
            web_calls += 1
            search_rounds_total += 1
            attempts = list(search.get('attempts') or [])
            all_attempts.extend(attempts)
            model = _text(search.get('model'))
            if model:
                component_models.append(model)
                if model not in used_models:
                    used_models.append(model)
            search_status = _text(search.get('status'), 'ERROR')
            rounds.append({'round': round_index, 'intent': search_intent, 'status': search_status, 'model': model or None, 'attempts': attempts})
            if search_status == 'RATE_LIMITED':
                rate_limited = True
                emit(f'    ronda {round_index} ({search_intent}): RATE_LIMITED · {_attempt_summary(attempts)}')
                break
            message = search.get('message')
            if message is None:
                emit(f'    ronda {round_index} ({search_intent}): {search_status} · {_attempt_summary(attempts)}')
                continue
            valid = _annotated_valid_results(comp, message, year, search_intent=search_intent)
            accumulated = _merge_results(accumulated, valid)
            profile = _evidence_profile(comp, accumulated)
            any_search = any_search or bool(search.get('search_executed'))
            emit(f"    ronda {round_index} ({search_intent}): modelo={model or 'N/A'} · fuentes={profile['source_count']} (componente={profile['component_sources']}, contexto={profile['context_sources']}, hosts={profile['independent_hosts']})")
            if profile.get('sufficient'):
                break
        profile = _evidence_profile(comp, accumulated)
        if not accumulated or not profile.get('sufficient'):
            status = 'RATE_LIMITED' if rate_limited and (not accumulated) else 'INSUFFICIENT_EVIDENCE' if accumulated else search_status
            reason = 'Groq alcanzó el límite temporal de solicitudes antes de obtener evidencia específica suficiente. CorePulse no inventa una clasificación y conserva NO EVALUABLE.' if status == 'RATE_LIMITED' else 'CorePulse investigó este componente de forma independiente, pero todavía no reunió evidencia específica y contexto mainstream suficientes desde fuentes independientes para una clasificación defendible.'
            row_sources = list(dict.fromkeys((_clean_source_url(x.get('url')) for x in accumulated if _clean_source_url(x.get('url')))))[:8]
            rows_by_id[cid] = {'component_id': cid, 'component_type': ctype, 'detected_hardware': comp['detected_hardware'], 'classification': 'NO_EVALUABLE', 'confidence': 'BAJA', 'reason': reason, 'sources': row_sources, 'source_count': len(row_sources), 'research_status': status, 'research_model': component_models[-1] if component_models else None, 'search_rounds': rounds, 'evidence_profile': profile}
            component_trace.append({'component_id': cid, 'status': status, 'models': list(dict.fromkeys(component_models)), 'source_count': len(row_sources), 'search_rounds': rounds, 'evidence_profile': profile})
            emit('    resultado: NO EVALUABLE · evidencia insuficiente')
            continue
        classification = _classify_from_verified_evidence(Groq=Groq, api_key=api_key, available_models=available_models, comp=comp, year=year, results=accumulated)
        cls = _text(classification.get('classification'), 'NO_EVALUABLE').upper()
        conf = _text(classification.get('confidence'), 'BAJA').upper()
        why = _text(classification.get('reason')) or _fixed_reason(comp, year, cls, classification.get('evidence_axes') or {}, profile)
        conf = _confidence_ceiling(conf, accumulated)
        if cls != 'NO_EVALUABLE':
            evaluable += 1
        classifier_model = _text(classification.get('model')) or None
        if classifier_model and classifier_model not in classifier_models:
            classifier_models.append(classifier_model)
        row_sources = list(dict.fromkeys((_clean_source_url(x.get('url')) for x in accumulated if _clean_source_url(x.get('url')))))[:8]
        for url in row_sources:
            if url not in all_sources:
                all_sources.append(url)
        research_status = 'OK' if cls != 'NO_EVALUABLE' else 'INSUFFICIENT_COMPARATIVE_CONTEXT'
        rows_by_id[cid] = {'component_id': cid, 'component_type': ctype, 'detected_hardware': comp['detected_hardware'], 'classification': cls, 'confidence': conf, 'reason': why, 'sources': row_sources, 'source_count': len(row_sources), 'research_status': research_status, 'research_model': component_models[-1] if component_models else None, 'research_models': list(dict.fromkeys(component_models)), 'classifier_model': classifier_model, 'decision_method': classification.get('decision_method'), 'decision_score': classification.get('decision_score'), 'evidence_axes': classification.get('evidence_axes') if isinstance(classification.get('evidence_axes'), dict) else {}, 'extractor_model': classification.get('extractor_model'), 'extraction_status': classification.get('extraction_status'), 'extraction_error': classification.get('extraction_error'), 'extraction_attempts': list(classification.get('extraction_attempts') or []), 'confidence_score': classification.get('confidence_score'), 'confidence_basis': classification.get('confidence_basis'), 'search_rounds': rounds, 'evidence_profile': profile}
        component_trace.append({'component_id': cid, 'status': research_status, 'models': list(dict.fromkeys(component_models)), 'classifier_model': classifier_model, 'source_count': len(row_sources), 'search_rounds': rounds, 'evidence_profile': profile})
        emit(f"    resultado: {cls} · confianza={conf} · extractor={classification.get('extraction_status') or 'N/A'}")
    rows = [rows_by_id[c['component_id']] for c in clean if c['component_id'] in rows_by_id]
    unique_models = list(dict.fromkeys(used_models))
    aggregate_model = None if not unique_models else unique_models[0] if len(unique_models) == 1 else 'MIXED: ' + ' + '.join(unique_models)
    excluded_domain = len(clean) - len(domain_components)
    identity_skipped = len(domain_components) - actually_researched
    reason = f'Vigencia {int(year)} investigada con motor universal determinista y control de cuota; {evaluable}/{len(domain_components)} componente(s) del dominio pudieron clasificarse.'
    if identity_skipped:
        reason += f' {identity_skipped} componente(s) quedaron NO EVALUABLE por identidad insuficiente.'
    if rate_limited:
        reason += ' Se detectó HTTP 429 y CorePulse detuvo reintentos agresivos para preservar la cuota y la evidencia ya obtenida.'
    if excluded_domain:
        reason += f' {excluded_domain} componente(s) adicional(es) no pertenecen al dominio de vigencia anual.'
    status = 'PARTIAL_RATE_LIMITED' if rate_limited and any_search else 'OK' if any_search else 'RATE_LIMITED' if rate_limited else 'ERROR'
    return {'status': status, 'capability': 'AVAILABLE', 'model': aggregate_model, 'models_used': unique_models, 'classifier_models': list(dict.fromkeys(classifier_models)), 'hardware_relevance': rows, 'evaluable_count': evaluable, 'researchable_count': len(domain_components), 'actually_researched_count': actually_researched, 'search_rounds_total': search_rounds_total, 'web_search_calls': web_calls, 'web_search_budget': max_web_calls, 'component_count': len(rows), 'sources': all_sources[:50], 'source_count': len(all_sources[:50]), 'reason': reason, 'attempts': all_attempts, 'component_research': component_trace, 'request_mode': 'per_component_staged_research_v4', 'request_bytes': None, 'search_executed': any_search, 'visit_executed': False, 'executed_tools_count': sum((int(a.get('executed_tools_count') or 0) for a in all_attempts)), 'tool_types': ['search'] if any_search else [], 'tool_evidence_available': any_search, 'evidence_chars': None, 'rate_limited': rate_limited}
try:
    __all__ = list(dict.fromkeys(list(__all__) + ['_retry_after_provider', '_pace_provider', '_simple_local_axes', '_ram_local_axes']))
except Exception:
    pass
import hashlib as _hashlib
from pathlib import Path as _Path
from datetime import datetime as _datetime, timezone as _timezone

def _parse_duration_seconds(value: Any) -> float:
    text = _text(value).lower().strip()
    if not text:
        return 0.0
    try:
        return max(0.0, float(text))
    except Exception:
        pass
    total = 0.0
    matched = False
    for amount, unit in re.findall('([0-9]+(?:\\.[0-9]+)?)\\s*(ms|s|m|h)', text):
        matched = True
        number = float(amount)
        if unit == 'ms':
            total += number / 1000.0
        elif unit == 's':
            total += number
        elif unit == 'm':
            total += number * 60.0
        elif unit == 'h':
            total += number * 3600.0
    return max(0.0, total) if matched else 0.0

def _retry_after_provider(exc: Exception) -> float:
    """Gestiona la operación `retry_after_provider` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    response = getattr(exc, 'response', None)
    headers = getattr(response, 'headers', None)
    if headers:
        for key in ('retry-after', 'Retry-After'):
            try:
                raw = headers.get(key)
            except Exception:
                raw = None
            seconds = _parse_duration_seconds(raw)
            if seconds > 0:
                return seconds
        for key in ('x-ratelimit-reset-tokens', 'x-ratelimit-reset-requests'):
            try:
                raw = headers.get(key)
            except Exception:
                raw = None
            seconds = _parse_duration_seconds(raw)
            if seconds > 0:
                return seconds
    text = str(exc)
    for pat in ('retry[^0-9]{0,30}([0-9]+(?:\\.[0-9]+)?)\\s*s', 'try again in\\s*([0-9]+(?:\\.[0-9]+)?)\\s*s?'):
        m = re.search(pat, text, re.I)
        if m:
            try:
                return max(0.0, float(m.group(1)))
            except Exception:
                pass
    return _retry_after_provider_base(exc)

_CACHE_SCHEMA = 2

def _cache_path() -> _Path:
    custom = _text(os.getenv('COREPULSE_AI_RELEVANCE_CACHE_PATH'))
    if custom:
        return _Path(custom).expanduser()
    return _Path(__file__).resolve().parents[1] / 'data' / 'ai_relevance_cache.json'

def _stable_facts(comp: Dict[str, Any]) -> Dict[str, Any]:
    facts = comp.get('facts') if isinstance(comp.get('facts'), dict) else {}
    allowed = {'CPU': ('cores', 'threads', 'max_clock_ghz'), 'GPU': ('vram_gb', 'vendor', 'video_processor'), 'RAM': ('total_gb', 'module_count', 'configured_speeds_mhz'), 'STORAGE': ('capacity_gb', 'interface', 'media_type')}.get(_text(comp.get('type') or comp.get('component_type')).upper(), tuple(sorted(facts)))
    return {k: facts.get(k) for k in allowed if facts.get(k) not in (None, '', [], {})}

def _cache_key(comp: Dict[str, Any], year: int) -> str:
    payload = {'year': int(year), 'type': _text(comp.get('type') or comp.get('component_type')).upper(), 'name': _text(comp.get('name') or comp.get('detected_hardware')).lower(), 'facts': _stable_facts(comp)}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return _hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _save_cache(cache: Dict[str, Any]) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(path)
    except Exception:
        pass

def _cache_age_days(entry: Dict[str, Any]) -> Optional[float]:
    raw = _text(entry.get('saved_at_utc'))
    if not raw:
        return None
    try:
        stamp = _datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=_timezone.utc)
        return max(0.0, (_datetime.now(_timezone.utc) - stamp).total_seconds() / 86400.0)
    except Exception:
        return None

def _cached_row(cache: Dict[str, Any], comp: Dict[str, Any], year: int) -> Optional[Dict[str, Any]]:
    entry = (cache.get('entries') or {}).get(_cache_key(comp, year))
    if not isinstance(entry, dict):
        return None
    age = _cache_age_days(entry)
    ttl = _env_float('COREPULSE_AI_RELEVANCE_CACHE_DAYS', 14.0, 0.0, 90.0)
    if age is None or age > ttl:
        return None
    row = entry.get('row') if isinstance(entry.get('row'), dict) else None
    if not row or _text(row.get('classification')).upper() == 'NO_EVALUABLE':
        return None
    out = dict(row)
    out['research_status'] = 'CACHE_VERIFIED'
    out['cache_hit'] = True
    out['cache_age_days'] = round(age, 3)
    return out


def research_hardware_relevance(*, api_key: str, available_models: Iterable[str], components: List[Dict[str, Any]], year: int, progress_callback=None) -> Dict[str, Any]:
    """Investiga la operación `research_hardware_relevance` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    comps = [c for c in components or [] if isinstance(c, dict)]
    cache = _load_cache()
    cached_rows: Dict[str, Dict[str, Any]] = {}
    misses: List[Dict[str, Any]] = []
    domain = {'CPU', 'GPU', 'RAM', 'STORAGE'}

    def emit(text: str) -> None:
        if callable(progress_callback):
            try:
                progress_callback(text)
            except Exception:
                pass
    for comp in comps:
        cid = _text(comp.get('id') or comp.get('component_id'))
        ctype = _text(comp.get('type') or comp.get('component_type')).upper()
        if ctype in domain:
            row = _cached_row(cache, comp, year)
            if row is not None and cid:
                cached_rows[cid] = row
                emit(f"[CACHE] {ctype} · {_text(comp.get('name') or comp.get('detected_hardware'))} · vigencia verificada reutilizada ({row.get('cache_age_days', 0):.2f} días)")
                continue
        misses.append(comp)
    live = _research_hardware_relevance_live(api_key=api_key, available_models=available_models, components=misses, year=year, progress_callback=progress_callback) if misses else {'status': 'OK', 'capability': 'AVAILABLE', 'model': None, 'models_used': [], 'classifier_models': [], 'hardware_relevance': [], 'evaluable_count': 0, 'researchable_count': 0, 'actually_researched_count': 0, 'search_rounds_total': 0, 'web_search_calls': 0, 'web_search_budget': int(_env_float('COREPULSE_AI_MAX_WEB_SEARCH_CALLS', 12, 1, 18)), 'sources': [], 'source_count': 0, 'reason': 'Todos los componentes clasificables se resolvieron desde caché verificada.', 'attempts': [], 'component_research': [], 'request_mode': 'verified_cache_only', 'search_executed': False, 'rate_limited': False}
    live_rows = {_text(r.get('component_id')): dict(r) for r in live.get('hardware_relevance') or [] if isinstance(r, dict) and _text(r.get('component_id'))}
    recovered = _recover_failed_live_rows(cache, comps, live_rows, year)
    saved = 0
    comp_by_id = {_text(c.get('id') or c.get('component_id')): c for c in comps if _text(c.get('id') or c.get('component_id'))}
    for cid, row in live_rows.items():
        comp = comp_by_id.get(cid)
        if comp and _cache_row(cache, comp, year, row):
            saved += 1
    if saved:
        _save_cache(cache)
    merged_rows: List[Dict[str, Any]] = []
    for comp in comps:
        cid = _text(comp.get('id') or comp.get('component_id'))
        if cid in cached_rows:
            merged_rows.append(cached_rows[cid])
        elif cid in live_rows:
            merged_rows.append(live_rows[cid])
    researchable = sum((1 for c in comps if _text(c.get('type') or c.get('component_type')).upper() in domain))
    evaluable = sum((1 for r in merged_rows if _text(r.get('component_type')).upper() in domain and _text(r.get('classification')).upper() != 'NO_EVALUABLE'))
    sources: List[str] = []
    for row in merged_rows:
        for url in row.get('sources') or []:
            clean = _clean_source_url(url)
            if clean and clean not in sources:
                sources.append(clean)
    cache_hits = len(cached_rows)
    rate_limited = bool(live.get('rate_limited'))
    if rate_limited and evaluable > 0:
        status = 'PARTIAL_RATE_LIMITED'
    elif rate_limited:
        status = 'RATE_LIMITED'
    else:
        status = 'OK' if evaluable > 0 or researchable == 0 or cache_hits > 0 else _text(live.get('status'), 'ERROR')
    models = list(dict.fromkeys([_text(x) for x in live.get('models_used') or [] if _text(x)]))
    aggregate_model = live.get('model')
    if cache_hits and (not models):
        aggregate_model = 'CACHE_VERIFIED'
    reason = f'Vigencia {int(year)}: {evaluable}/{researchable} componente(s) clasificables; {cache_hits} resultado(s) reutilizados desde caché verificada.'
    if rate_limited:
        reason += ' Groq devolvió HTTP 429; CorePulse respetó retry-after y evitó reintentos agresivos.'
    elif saved:
        reason += f' Se guardaron {saved} resultado(s) verificados para evitar búsquedas repetidas en diagnósticos posteriores.'
    out = dict(live)
    out.update({'status': status, 'model': aggregate_model, 'hardware_relevance': merged_rows, 'evaluable_count': evaluable, 'researchable_count': researchable, 'component_count': len(merged_rows), 'sources': sources[:50], 'source_count': len(sources[:50]), 'reason': reason, 'request_mode': _RELEVANCE_ROUTE_ID, 'rate_limited': rate_limited, 'cache_hits': cache_hits, 'reference_recoveries': recovered, 'cache_entries_saved': saved, 'cache_path': str(_cache_path()), 'cache_ttl_days': _env_float('COREPULSE_AI_RELEVANCE_CACHE_DAYS', 14.0, 0.0, 90.0)})
    return out
try:
    __all__ = list(dict.fromkeys(list(__all__) + ['_parse_duration_seconds', '_cache_path']))
except Exception:
    pass
_DECISION_METHOD_BROWSER = 'COREPULSE_DETERMINISTIC_RUBRIC_V3_BROWSER_RESPONSES'
from types import SimpleNamespace as _SimpleNamespace
_RESPONSES_BROWSER_MODELS = ('openai/gpt-oss-20b', 'openai/gpt-oss-120b')
_RESPONSES_ENDPOINT = 'https://api.groq.com/openai/v1/responses'
_BROWSER_STATE: Dict[str, Any] = {'preferred_model': None, 'disabled_models': set(), 'last_call_at': 0.0}

def _dictify(value: Any) -> Any:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return [_dictify(x) for x in value]
    for name in ('model_dump', 'dict'):
        fn = getattr(value, name, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    return value

def _provider_error_message(data: Any) -> str:
    obj = _dictify(data)
    if isinstance(obj, dict):
        err = obj.get('error')
        if isinstance(err, dict):
            msg = _text(err.get('message'))
            typ = _text(err.get('type'))
            code = _text(err.get('code'))
            failed = err.get('failed_generation')
            parts = [x for x in (msg, typ, code) if x]
            if failed:
                parts.append(_text(failed))
            if parts:
                return ' | '.join(parts)[:900]
        msg = _text(obj.get('message'))
        if msg:
            return msg[:900]
    return _text(obj)[:900] or 'Error de proveedor sin detalle.'

def _responses_post(*, api_key: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    """Gestiona la operación `responses_post` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    try:
        import httpx
    except Exception as exc:
        return {'status_code': 0, 'headers': {}, 'data': {'error': {'message': f'httpx no disponible: {type(exc).__name__}'}}}
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json', 'User-Agent': f"CorePulse/{VERSION.lstrip('V')}"}
    try:
        response = httpx.post(_RESPONSES_ENDPOINT, headers=headers, json=payload, timeout=timeout)
        try:
            data = response.json()
        except Exception:
            data = {'raw': response.text[:4000]}
        return {'status_code': int(response.status_code), 'headers': dict(response.headers), 'data': data}
    except Exception as exc:
        return {'status_code': 0, 'headers': {}, 'data': {'error': {'message': _safe_error(exc)}}}

def _annotation_url(annotation: Dict[str, Any]) -> tuple[str, str]:
    if not isinstance(annotation, dict):
        return ('', '')
    nested = annotation.get('url_citation')
    if isinstance(nested, dict):
        return (_clean_source_url(nested.get('url')), _text(nested.get('title')))
    return (_clean_source_url(annotation.get('url')), _text(annotation.get('title')))

def _responses_message(data: Any) -> tuple[Any, Dict[str, Any]]:
    """Gestiona la operación `responses_message` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    obj = _dictify(data)
    if not isinstance(obj, dict):
        return (_SimpleNamespace(content='', executed_tools=[]), {'search_executed': False, 'tool_evidence_available': False, 'executed_tools_count': 0, 'tool_types': [], 'evidence_chars': 0, 'response_status': 'INVALID_RESPONSE', 'citation_count': 0})
    output = obj.get('output') if isinstance(obj.get('output'), list) else []
    text_chunks: List[str] = []
    citations: List[Dict[str, Any]] = []
    raw_results: List[Dict[str, Any]] = []
    search_call_seen = False
    for item_raw in output:
        item = _dictify(item_raw)
        if not isinstance(item, dict):
            continue
        typ = _text(item.get('type')).lower()
        if 'browser_search' in typ or 'web_search' in typ or typ in {'search', 'browser_search_call'}:
            search_call_seen = True
        for key in ('results', 'search_results'):
            raw = item.get(key)
            if isinstance(raw, dict) and isinstance(raw.get('results'), list):
                raw = raw.get('results')
            if isinstance(raw, list):
                for r in raw:
                    rr = _dictify(r)
                    if isinstance(rr, dict):
                        raw_results.append(rr)
        content = item.get('content')
        if not isinstance(content, list):
            continue
        for part_raw in content:
            part = _dictify(part_raw)
            if not isinstance(part, dict):
                continue
            txt = _text(part.get('text'))
            if txt:
                text_chunks.append(txt)
            anns = part.get('annotations')
            if isinstance(anns, list):
                for ann_raw in anns:
                    ann = _dictify(ann_raw)
                    if not isinstance(ann, dict):
                        continue
                    url, title = _annotation_url(ann)
                    if not url:
                        continue
                    start = ann.get('start_index')
                    end = ann.get('end_index')
                    snippet = ''
                    if txt:
                        try:
                            s = max(0, int(start) - 500) if start is not None else 0
                            e = min(len(txt), int(end) + 500) if end is not None else min(len(txt), 1200)
                            snippet = txt[s:e]
                        except Exception:
                            snippet = txt[:1200]
                    citations.append({'url': url, 'title': title, 'content': snippet, 'score': None})
    output_text = _text(obj.get('output_text'))
    if output_text:
        text_chunks.append(output_text)
    combined = '\n'.join((x for x in text_chunks if x)).strip()
    results: List[Dict[str, Any]] = []
    seen = set()
    for rr in raw_results:
        url = _clean_source_url(rr.get('url') or rr.get('link'))
        item = {'url': url, 'title': _text(rr.get('title')), 'content': _text(rr.get('content') or rr.get('snippet') or rr.get('text'))[:2400], 'score': rr.get('score')}
        key = item['url'] or item['title'] + '|' + item['content'][:120]
        if key and key not in seen:
            seen.add(key)
            results.append(item)
    for cite in citations:
        key = cite['url']
        if not key or key in seen:
            continue
        seen.add(key)
        if not cite.get('content'):
            cite['content'] = combined[:1800]
        results.append(cite)
    if not results and search_call_seen and combined:
        for url in sorted(_evidence_urls(combined)):
            results.append({'url': _clean_source_url(url), 'title': '', 'content': combined[:1800], 'score': None})
    search_executed = bool(search_call_seen or citations or raw_results)
    evidence_ok = bool(search_executed and results)
    tools = []
    if search_executed:
        tools.append({'type': 'search', 'output': combined[:5000], 'search_results': {'results': results}})
    message = _SimpleNamespace(content=combined, executed_tools=tools)
    trace = {'search_executed': search_executed, 'visit_executed': False, 'tool_evidence_available': evidence_ok, 'executed_tools_count': len(tools), 'tool_types': ['search'] if search_executed else [], 'evidence_chars': len(combined), 'response_status': _text(obj.get('status'), 'completed'), 'citation_count': len(results)}
    return (message, trace)

def _browser_models(available_models: Iterable[str]) -> List[str]:
    available = {str(x) for x in available_models if _text(x)}
    candidates = [m for m in _RESPONSES_BROWSER_MODELS if not available or m in available]
    preferred = _text(_BROWSER_STATE.get('preferred_model'))
    disabled = set(_BROWSER_STATE.get('disabled_models') or set())
    candidates = [m for m in candidates if m not in disabled]
    if preferred in candidates:
        candidates.remove(preferred)
        candidates.insert(0, preferred)
    return candidates

def _pace_browser() -> None:
    interval = _env_float('COREPULSE_AI_BROWSER_MIN_INTERVAL_SECONDS', 3.0, 0.0, 20.0)
    while True:
        now = _time.monotonic()
        last = float(_BROWSER_STATE.get('last_call_at') or 0.0)
        with _ROUTE_LOCK:
            blocked = float(_ROUTE_STATE.get('blocked_until') or 0.0)
        wait = max(last + interval - now, blocked - now, 0.0)
        if wait <= 0:
            _BROWSER_STATE['last_call_at'] = now
            return
        _time.sleep(min(wait, 1.0))

def _responses_browser_attempt(*, api_key: str, model: str, prompt: str, timeout: float) -> Dict[str, Any]:
    payload = {'model': model, 'input': prompt, 'tool_choice': 'required', 'tools': [{'type': 'browser_search'}], 'reasoning': {'effort': 'low'}, 'max_output_tokens': int(_env_float('COREPULSE_AI_BROWSER_MAX_OUTPUT_TOKENS', 900, 400, 2400))}
    request_bytes = _request_size_bytes(payload)
    _pace_browser()
    raw = _responses_post(api_key=api_key, payload=payload, timeout=timeout)
    code = int(raw.get('status_code') or 0)
    headers = raw.get('headers') if isinstance(raw.get('headers'), dict) else {}
    data = raw.get('data')
    if 200 <= code < 300:
        message, trace = _responses_message(data)
        verified = bool(trace.get('search_executed') and trace.get('tool_evidence_available'))
        return {'status': 'OK' if verified else 'AVAILABLE_NOT_EXECUTED', 'model': model, 'mode': 'responses_browser_search', 'http_status': code, 'request_bytes': request_bytes, 'message': message, 'headers': headers, **trace, 'error': None if verified else 'Responses API completó, pero no expuso citas/resultados verificables.'}
    status = 'ERROR_RATE_LIMIT_429' if code == 429 else 'ERROR_PROVIDER_413' if code == 413 else 'ERROR_UNSUPPORTED_ROUTE' if code in {400, 404, 405, 422} else 'ERROR'
    return {'status': status, 'model': model, 'mode': 'responses_browser_search', 'http_status': code or None, 'request_bytes': request_bytes, 'message': None, 'headers': headers, 'error': _provider_error_message(data), 'search_executed': False, 'tool_evidence_available': False, 'executed_tools_count': 0, 'tool_types': [], 'evidence_chars': 0}

def _retry_after_attempt(attempt: Dict[str, Any]) -> float:
    headers = attempt.get('headers') if isinstance(attempt.get('headers'), dict) else {}
    for key in ('retry-after', 'Retry-After', 'x-ratelimit-reset-tokens'):
        raw = headers.get(key)
        seconds = _parse_duration_seconds(raw)
        if seconds > 0:
            return seconds
    return 0.0

def _legacy_compound_fallback(*, Groq, api_key: str, available_models: Iterable[str], prompt: str, timeout: float) -> Dict[str, Any]:
    """Gestiona la operación `legacy_compound_fallback` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    allow = _text(os.getenv('COREPULSE_AI_ALLOW_COMPOUND_RELEVANCE_FALLBACK', '1')).lower() not in {'0', 'false', 'off', 'no'}
    if not allow:
        return {'status': 'PROVIDER_ROUTE_EXHAUSTED', 'model': None, 'message': None, 'attempts': [], 'reason': 'Responses browser_search no estuvo disponible y el fallback Compound está desactivado.'}
    available = {str(x) for x in available_models if _text(x)}
    model = 'groq/compound-mini'
    if available and model not in available:
        return {'status': 'PROVIDER_ROUTE_EXHAUSTED', 'model': None, 'message': None, 'attempts': [], 'reason': 'La cuenta no expone groq/compound-mini como fallback.'}
    try:
        client = _new_client(Groq, api_key, timeout)
        kwargs = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'max_completion_tokens': 600, 'compound_custom': {'tools': {'enabled_tools': ['web_search']}}, 'search_settings': {'exclude_domains': list(NOISY_SEARCH_DOMAINS)}}
        _pace_provider()
        response = client.chat.completions.create(**kwargs)
        message = response.choices[0].message if response and response.choices else None
        if message is None:
            raise RuntimeError('Groq Compound Mini no devolvió message/choices.')
        trace = _tool_trace(message)
        verified = bool(trace.get('search_executed') and trace.get('tool_evidence_available'))
        attempt = {'model': model, 'mode': 'compound_mini_last_fallback', 'status': 'OK' if verified else 'NO_VERIFIED_SEARCH', 'http_status': 200, 'request_bytes': _request_size_bytes(kwargs), **trace}
        return {'status': 'OK' if verified else 'AVAILABLE_NOT_EXECUTED', 'capability': 'AVAILABLE', 'model': model, 'message': message, 'attempts': [attempt], 'request_mode': 'compound_mini_last_fallback', 'request_bytes': attempt['request_bytes'], **trace, 'reason': 'Fallback Compound Mini verificado.' if verified else 'Compound Mini respondió sin evidencia web verificable.'}
    except Exception as exc:
        code = _error_status_code(exc)
        status = 'ERROR_RATE_LIMIT_429' if code == 429 else 'ERROR_PROVIDER_413' if code == 413 else 'ERROR'
        if code == 429:
            _mark_rate_limited(exc)
        attempt = {'model': model, 'mode': 'compound_mini_last_fallback', 'status': status, 'http_status': code, 'error': _safe_error(exc)}
        return {'status': 'RATE_LIMITED' if code == 429 else status, 'capability': 'AVAILABLE', 'model': model, 'message': None, 'attempts': [attempt], 'request_mode': 'compound_mini_last_fallback', 'search_executed': False, 'tool_evidence_available': False, 'executed_tools_count': 0, 'tool_types': [], 'reason': f'Fallback Compound Mini falló: {status}.'}

try:
    __all__ = list(dict.fromkeys(list(__all__) + ['_responses_post', '_responses_message', '_responses_browser_attempt']))
except Exception:
    pass

# ---------------------------------------------------------------------------
# la ruta de proveedor - Relevance Provider Route Fix
# Prioriza Compound Mini Basic Web Search para investigación por componente,
# usa GPT-OSS Chat Browser Search como fallback y evita que un 429 local
# invalide automáticamente todos los componentes siguientes.
# ---------------------------------------------------------------------------

_COMPOUND_API_VERSION = '2025-07-23'
_PROVIDER_ROUTE_ID = 'universal_compact_websearch'




def _provider_compound_basic_attempt(*, Groq, api_key: str, prompt: str, timeout: float) -> Dict[str, Any]:
    """Web Search básico de Compound Mini, con resultados crudos verificables."""
    try:
        try:
            client = Groq(
                api_key=api_key,
                timeout=timeout,
                default_headers={'Groq-Model-Version': _COMPOUND_API_VERSION},
            )
        except TypeError:
            # Compatibilidad con SDKs Groq antiguos. Si no acepta default_headers,
            # mantenemos la ruta; el fallback GPT-OSS sigue disponible ante 413.
            client = Groq(api_key=api_key, timeout=timeout)
        kwargs = {
            'model': 'groq/compound-mini',
            'messages': [{'role': 'user', 'content': prompt}],
            'max_completion_tokens': int(_env_float('COREPULSE_AI_COMPOUND_MAX_COMPLETION_TOKENS', 450, 250, 900)),
            'compound_custom': {'tools': {'enabled_tools': ['web_search']}},
            'search_settings': {'exclude_domains': list(NOISY_SEARCH_DOMAINS)},
        }
        _pace_provider()
        response = client.chat.completions.create(**kwargs)
        message = response.choices[0].message if response and response.choices else None
        if message is None:
            raise RuntimeError('Groq Compound Mini no devolvió message/choices.')
        trace = _tool_trace(message)
        verified = bool(trace.get('search_executed') and trace.get('tool_evidence_available'))
        return {
            'status': 'OK' if verified else 'AVAILABLE_NOT_EXECUTED',
            'model': 'groq/compound-mini',
            'mode': 'compound_mini_basic_web_search',
            'http_status': 200,
            'request_bytes': _request_size_bytes(kwargs),
            'message': message,
            **trace,
            'error': None if verified else 'Compound Mini respondió sin resultados web verificables.',
        }
    except Exception as exc:
        code = _error_status_code(exc)
        status = 'ERROR_RATE_LIMIT_429' if code == 429 else 'ERROR_PROVIDER_413' if code == 413 else 'ERROR'
        return {
            'status': status,
            'model': 'groq/compound-mini',
            'mode': 'compound_mini_basic_web_search',
            'http_status': code,
            'message': None,
            'error': _safe_error(exc),
            'retry_after_seconds': _retry_after_provider_base(exc) if code == 429 else 0.0,
            'search_executed': False,
            'tool_evidence_available': False,
            'executed_tools_count': 0,
            'tool_types': [],
            'evidence_chars': 0,
        }


def _provider_gptoss_chat_browser_attempt(*, Groq, api_key: str, available_models: Iterable[str], prompt: str, timeout: float) -> Dict[str, Any]:
    """Fallback documentado: GPT-OSS Chat Completions + browser_search."""
    available = {str(x) for x in available_models if _text(x)}
    candidates = [m for m in ('openai/gpt-oss-20b', 'openai/gpt-oss-120b') if not available or m in available]
    if not candidates:
        return {'status': 'PROVIDER_ROUTE_EXHAUSTED', 'model': None, 'mode': 'gptoss_chat_browser_search', 'message': None, 'error': 'No hay GPT-OSS con Browser Search disponible.'}
    attempts = []
    for model in candidates:
        try:
            client = Groq(api_key=api_key, timeout=timeout)
            kwargs = {
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'tool_choice': 'required',
                'tools': [{'type': 'browser_search'}],
                'max_completion_tokens': int(_env_float('COREPULSE_AI_BROWSER_MAX_OUTPUT_TOKENS', 1000, 500, 1800)),
                'reasoning_effort': 'low',
                'include_reasoning': False,
            }
            _pace_provider()
            response = client.chat.completions.create(**kwargs)
            message = response.choices[0].message if response and response.choices else None
            if message is None:
                raise RuntimeError(f'{model} no devolvió message/choices.')
            trace = _tool_trace(message)
            verified = bool(trace.get('search_executed') and trace.get('tool_evidence_available'))
            attempt = {
                'status': 'OK' if verified else 'AVAILABLE_NOT_EXECUTED',
                'model': model,
                'mode': 'gptoss_chat_browser_search',
                'http_status': 200,
                'request_bytes': _request_size_bytes(kwargs),
                'message': message,
                **trace,
                'error': None if verified else 'GPT-OSS respondió sin resultados web verificables.',
            }
            attempts.append({k: v for k, v in attempt.items() if k != 'message'})
            if verified:
                attempt['attempts'] = attempts
                return attempt
        except Exception as exc:
            code = _error_status_code(exc)
            status = 'ERROR_RATE_LIMIT_429' if code == 429 else 'ERROR_PROVIDER_413' if code == 413 else 'ERROR_UNSUPPORTED_ROUTE' if code in {400, 404, 405, 422} else 'ERROR'
            attempts.append({'status': status, 'model': model, 'mode': 'gptoss_chat_browser_search', 'http_status': code, 'error': _safe_error(exc)})
            if code == 429:
                return {'status': status, 'model': model, 'mode': 'gptoss_chat_browser_search', 'message': None, 'attempts': attempts, 'retry_after_seconds': _retry_after_provider_base(exc), 'error': _safe_error(exc)}
            continue
    return {'status': 'PROVIDER_ROUTE_EXHAUSTED', 'model': attempts[-1].get('model') if attempts else None, 'mode': 'gptoss_chat_browser_search', 'message': None, 'attempts': attempts, 'error': 'GPT-OSS Browser Search no produjo evidencia verificable.'}


def _provider_wait_after_429(seconds: float) -> float:
    """Espera localmente; no bloquea globalmente a los demás componentes."""
    max_wait = _env_float('COREPULSE_AI_MAX_429_WAIT_SECONDS', 18.0, 2.0, 45.0)
    wait = float(seconds or 0.0)
    if wait <= 0:
        wait = _env_float('COREPULSE_AI_429_LOCAL_RETRY_SECONDS', 5.0, 2.0, 15.0)
    wait = min(wait + 0.35, max_wait)
    _time.sleep(wait)
    return wait


def _compound_web_search(*, Groq, api_key: str, available_models: Iterable[str], prompt: str, timeout: float=45.0) -> Dict[str, Any]:
    """la ruta de proveedor route policy.

    1) Compound Mini BASIC web_search (una búsqueda, raw search_results).
    2) Si falla/no ejecuta, GPT-OSS Chat browser_search.
    3) Un 429 se espera/reintenta localmente una vez; NO deja `blocked_until`
       activo para condenar RAM/GPU/SSD después de un fallo de CPU.
    """
    if not api_key:
        return {'status': 'UNAVAILABLE', 'capability': 'UNAVAILABLE', 'model': None, 'message': None, 'attempts': [], 'reason': 'GROQ_API_KEY no configurada.'}
    cache_key = 'provider_route|' + _text(prompt)
    with _ROUTE_LOCK:
        cached = (_ROUTE_STATE.get('cache') or {}).get(cache_key)
        # El cooldown viejo de la capa por componente no se usa como abort global en la ruta de proveedor.
        _ROUTE_STATE['blocked_until'] = 0.0
    if isinstance(cached, dict):
        out = dict(cached)
        out['cache_hit'] = True
        return out

    attempts: List[Dict[str, Any]] = []

    first = _provider_compound_basic_attempt(Groq=Groq, api_key=api_key, prompt=prompt, timeout=timeout)
    attempts.append({k: v for k, v in first.items() if k != 'message'})
    status = _text(first.get('status')).upper()
    if status == 'OK':
        result = {
            'status': 'OK', 'capability': 'AVAILABLE', 'model': first.get('model'), 'message': first.get('message'),
            'attempts': attempts, 'request_mode': _PROVIDER_ROUTE_ID, 'request_bytes': first.get('request_bytes'),
            'search_executed': True, 'visit_executed': False, 'tool_evidence_available': True,
            'executed_tools_count': int(first.get('executed_tools_count') or 1), 'tool_types': ['search'],
            'evidence_chars': int(first.get('evidence_chars') or 0),
            'reason': 'Compound Mini Basic Web Search entregó resultados verificables.'
        }
        with _ROUTE_LOCK:
            _ROUTE_STATE.setdefault('cache', {})[cache_key] = dict(result)
        return result

    if status == 'ERROR_RATE_LIMIT_429':
        waited = _provider_wait_after_429(float(first.get('retry_after_seconds') or 0.0))
        retry = _provider_compound_basic_attempt(Groq=Groq, api_key=api_key, prompt=prompt, timeout=timeout)
        attempts.append({k: v for k, v in retry.items() if k != 'message'})
        if _text(retry.get('status')).upper() == 'OK':
            return {
                'status': 'OK', 'capability': 'AVAILABLE', 'model': retry.get('model'), 'message': retry.get('message'),
                'attempts': attempts, 'request_mode': _PROVIDER_ROUTE_ID, 'search_executed': True,
                'visit_executed': False, 'tool_evidence_available': True,
                'executed_tools_count': int(retry.get('executed_tools_count') or 1), 'tool_types': ['search'],
                'evidence_chars': int(retry.get('evidence_chars') or 0), 'auto_retry_performed': True,
                'auto_retry_wait_seconds': round(waited, 2), 'recovered_from_429': True,
                'reason': 'Compound Mini se recuperó de HTTP 429 respetando una espera local.'
            }
        first = retry
        status = _text(first.get('status')).upper()
        # Tras el reintento se permite intentar el modelo/browser alternativo.

    browser = _provider_gptoss_chat_browser_attempt(
        Groq=Groq, api_key=api_key, available_models=available_models, prompt=prompt, timeout=timeout
    )
    browser_attempts = list(browser.get('attempts') or [])
    if not browser_attempts:
        browser_attempts = [{k: v for k, v in browser.items() if k not in {'message', 'attempts'}}]
    attempts.extend(browser_attempts)
    if _text(browser.get('status')).upper() == 'OK':
        result = {
            'status': 'OK', 'capability': 'AVAILABLE', 'model': browser.get('model'), 'message': browser.get('message'),
            'attempts': attempts, 'request_mode': _PROVIDER_ROUTE_ID, 'search_executed': True,
            'visit_executed': False, 'tool_evidence_available': True,
            'executed_tools_count': int(browser.get('executed_tools_count') or 1), 'tool_types': ['search'],
            'evidence_chars': int(browser.get('evidence_chars') or 0),
            'reason': 'GPT-OSS Chat Browser Search entregó resultados verificables como fallback.'
        }
        with _ROUTE_LOCK:
            _ROUTE_STATE.setdefault('cache', {})[cache_key] = dict(result)
        return result

    if _text(browser.get('status')).upper() == 'ERROR_RATE_LIMIT_429':
        waited = _provider_wait_after_429(float(browser.get('retry_after_seconds') or 0.0))
        retry_browser = _provider_gptoss_chat_browser_attempt(
            Groq=Groq, api_key=api_key, available_models=available_models, prompt=prompt, timeout=timeout
        )
        retry_attempts = list(retry_browser.get('attempts') or [])
        attempts.extend(retry_attempts)
        if _text(retry_browser.get('status')).upper() == 'OK':
            return {
                'status': 'OK', 'capability': 'AVAILABLE', 'model': retry_browser.get('model'), 'message': retry_browser.get('message'),
                'attempts': attempts, 'request_mode': _PROVIDER_ROUTE_ID, 'search_executed': True,
                'visit_executed': False, 'tool_evidence_available': True,
                'executed_tools_count': int(retry_browser.get('executed_tools_count') or 1), 'tool_types': ['search'],
                'evidence_chars': int(retry_browser.get('evidence_chars') or 0), 'auto_retry_performed': True,
                'auto_retry_wait_seconds': round(waited, 2), 'recovered_from_429': True,
                'reason': 'GPT-OSS Browser Search se recuperó de HTTP 429 con espera local.'
            }

    rate_limited = any(_text(a.get('status')).upper() == 'ERROR_RATE_LIMIT_429' for a in attempts if isinstance(a, dict))
    return {
        'status': 'RATE_LIMITED' if rate_limited else 'PROVIDER_ROUTE_EXHAUSTED',
        'capability': 'AVAILABLE',
        'model': attempts[-1].get('model') if attempts else None,
        'message': None,
        'attempts': attempts,
        'request_mode': _PROVIDER_ROUTE_ID,
        'search_executed': False,
        'visit_executed': False,
        'tool_evidence_available': False,
        'executed_tools_count': 0,
        'tool_types': [],
        'reason': ('Las rutas web fueron limitadas temporalmente por el proveedor; CorePulse no inventó evidencia.'
                   if rate_limited else 'Las rutas web disponibles no entregaron evidencia verificable para esta consulta.'),
    }

try:
    __all__ = list(dict.fromkeys(list(__all__) + [
        '_provider_compound_basic_attempt', '_provider_gptoss_chat_browser_attempt', '_PROVIDER_ROUTE_ID'
    ]))
except Exception:
    pass

# ---------------------------------------------------------------------------
# el extractor robusto · Extractor & Evidence Quality Fix
# - Reintenta/normaliza la extracción de ejes antes de caer a NO_EVALUABLE.
# - Prioriza fuentes oficiales/técnicas por componente sin relajar la rúbrica.
# - Conserva explicación concreta de contradicciones para trazabilidad/PDF.
# ---------------------------------------------------------------------------
import ast as _ast

_CACHE_SCHEMA = 5
_RELEVANCE_ROUTE_ID = 'universal_per_component_relevance'
_RELEVANCE_EXTRACTOR_SCHEMA = {
    'type': 'object',
    'properties': {
        'primary_position': {'type': 'string', 'enum': list(_POSITION_VALUES)},
        'secondary_position': {'type': 'string', 'enum': list(_POSITION_VALUES)},
        'tertiary_position': {'type': 'string', 'enum': list(_POSITION_VALUES)},
        'material_limitation': {'type': 'string', 'enum': ['YES', 'NO', 'UNKNOWN']},
        'evidence_conflict': {'type': 'boolean'},
        'conflict_reason': {'type': 'string'},
        'conflicting_axes': {
            'type': 'array',
            'items': {'type': 'string', 'enum': ['primary_position', 'secondary_position', 'tertiary_position', 'material_limitation']},
        },
        'basis': {'type': 'string'},
    },
    'required': [
        'primary_position', 'secondary_position', 'tertiary_position',
        'material_limitation', 'evidence_conflict', 'conflict_reason',
        'conflicting_axes', 'basis'
    ],
    'additionalProperties': False,
}


def _extract_json_relaxed(text: str) -> Optional[Dict[str, Any]]:
    """Extrae JSON tolerando fences, texto envolvente, comas finales y dict literal seguro."""
    parsed = _extract_json(text)
    if isinstance(parsed, dict):
        return parsed
    raw = _text(text)
    if not raw:
        return None
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.I | re.S).strip()
    a, b = raw.find('{'), raw.rfind('}')
    candidate = raw[a:b + 1] if a >= 0 and b > a else raw
    candidate = re.sub(r',\s*([}\]])', r'\1', candidate)
    try:
        obj = json.loads(candidate)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    try:
        obj = _ast.literal_eval(candidate)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _axis_value(value: Any) -> str:
    raw = _text(value, 'UNKNOWN').upper().replace('-', '_').replace(' ', '_')
    aliases = {
        'WELLABOVE': 'WELL_ABOVE', 'MUY_POR_ENCIMA': 'WELL_ABOVE', 'MUY_SUPERIOR': 'WELL_ABOVE',
        'POR_ENCIMA': 'ABOVE', 'SUPERIOR': 'ABOVE',
        'MEET': 'MEETS', 'MATCH': 'MEETS', 'MATCHES': 'MEETS', 'ON_PAR': 'MEETS', 'EN_LINEA': 'MEETS', 'ESTANDAR': 'MEETS', 'STANDARD': 'MEETS',
        'SLIGHTLYBELOW': 'SLIGHTLY_BELOW', 'ALGO_POR_DEBAJO': 'SLIGHTLY_BELOW', 'LIGERAMENTE_POR_DEBAJO': 'SLIGHTLY_BELOW',
        'FARBELOW': 'FAR_BELOW', 'MUY_POR_DEBAJO': 'FAR_BELOW', 'CLARAMENTE_POR_DEBAJO': 'FAR_BELOW',
        'N_A': 'UNKNOWN', 'NA': 'UNKNOWN', 'NONE': 'UNKNOWN', 'DESCONOCIDO': 'UNKNOWN',
    }
    raw = aliases.get(raw, raw)
    return raw if raw in _POSITION_VALUES else 'UNKNOWN'


def _yes_no_unknown(value: Any) -> str:
    if isinstance(value, bool):
        return 'YES' if value else 'NO'
    raw = _text(value, 'UNKNOWN').upper().strip()
    aliases = {'TRUE': 'YES', 'FALSE': 'NO', 'SI': 'YES', 'SÍ': 'YES', 'N': 'NO', 'Y': 'YES', 'NONE': 'UNKNOWN', 'N/A': 'UNKNOWN'}
    raw = aliases.get(raw, raw)
    return raw if raw in {'YES', 'NO', 'UNKNOWN'} else 'UNKNOWN'


def _truthy_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {'1', 'true', 'yes', 'si', 'sí', 'y'}


def _normalize_axes_payload(payload: Any) -> Dict[str, Any]:
    """Normaliza respuestas del extractor, incluso cuando vienen anidadas o con aliases."""
    obj = payload if isinstance(payload, dict) else {}
    for key in ('axes', 'evidence_axes', 'result', 'analysis', 'normalized_evidence'):
        nested = obj.get(key)
        if isinstance(nested, dict) and any(k in nested for k in ('primary_position', 'primary', 'position')):
            obj = nested
            break
    primary = obj.get('primary_position', obj.get('primary', obj.get('position')))
    secondary = obj.get('secondary_position', obj.get('secondary'))
    tertiary = obj.get('tertiary_position', obj.get('tertiary'))
    axes = {
        'primary_position': _axis_value(primary),
        'secondary_position': _axis_value(secondary),
        'tertiary_position': _axis_value(tertiary),
        'material_limitation': _yes_no_unknown(obj.get('material_limitation', obj.get('limitation'))),
        'evidence_conflict': _truthy_bool(obj.get('evidence_conflict', obj.get('conflict'))),
        'conflict_reason': _sanitize_reason(obj.get('conflict_reason') or obj.get('conflict_detail') or obj.get('contradiction_reason')),
        'basis': _sanitize_reason(obj.get('basis') or obj.get('reason') or obj.get('evidence_basis')),
    }
    raw_axes = obj.get('conflicting_axes') or obj.get('conflict_axes') or []
    if isinstance(raw_axes, str):
        raw_axes = [x.strip() for x in re.split(r'[,;|]', raw_axes) if x.strip()]
    allowed = {'primary_position', 'secondary_position', 'tertiary_position', 'material_limitation'}
    axes['conflicting_axes'] = [str(x) for x in raw_axes if str(x) in allowed] if isinstance(raw_axes, list) else []
    if not axes['evidence_conflict']:
        axes['conflict_reason'] = ''
        axes['conflicting_axes'] = []
    return axes


def _extract_axes_from_text(text: str) -> Dict[str, Any]:
    """Último parser tolerante: solo recupera valores explícitos, nunca los infiere."""
    raw = _text(text)
    if not raw:
        return {}
    parsed = _extract_json_relaxed(raw)
    if isinstance(parsed, dict):
        return _normalize_axes_payload(parsed)
    out: Dict[str, Any] = {}
    for key in ('primary_position', 'secondary_position', 'tertiary_position'):
        m = re.search(rf'(?i)\b{re.escape(key)}\b\s*[:=]\s*["\']?([A-Z_ -]+)', raw)
        if m:
            out[key] = _axis_value(m.group(1).strip())
    if out:
        out.setdefault('primary_position', 'UNKNOWN')
        out.setdefault('secondary_position', 'UNKNOWN')
        out.setdefault('tertiary_position', 'UNKNOWN')
        out.setdefault('material_limitation', 'UNKNOWN')
        out.setdefault('evidence_conflict', False)
        out.setdefault('conflict_reason', '')
        out.setdefault('conflicting_axes', [])
        out.setdefault('basis', '')
    return out


def _extract_axes_prompt(comp: Dict[str, Any], year: int, results: List[Dict[str, Any]]) -> str:
    ctype = _text(comp.get('component_type'), 'UNKNOWN').upper()
    facts = comp.get('facts') if isinstance(comp.get('facts'), dict) else {}
    return (
        f'Extrae evidencia NORMALIZADA para CorePulse. Año={int(year)}; tipo={ctype}; '
        f'hardware={_text(comp.get("detected_hardware"), "N/A")}; facts reales={json.dumps(facts, ensure_ascii=False, separators=(",", ":"))}.\n'
        f'Definiciones de ejes: {_axis_definitions(ctype)}\n'
        'Valores permitidos: WELL_ABOVE, ABOVE, MEETS, SLIGHTLY_BELOW, FAR_BELOW, UNKNOWN.\n'
        'No elijas la clasificación final. No uses conocimiento fuera de SOURCE/facts. '
        'No conviertas antigüedad por sí sola en bajo rendimiento. Compara con mainstream de la MISMA categoría, no solo flagship/high-end.\n'
        'material_limitation=YES solo si una limitación material actual está respaldada; NO si está descartada; UNKNOWN si falta evidencia.\n'
        'evidence_conflict=true SOLO si dos o más fuentes relevantes sostienen conclusiones materialmente incompatibles sobre un mismo eje. '
        'Si es true, conflict_reason debe resumir la discrepancia sin URLs y conflicting_axes debe indicar los ejes afectados. '
        'Si no existe contradicción material, evidence_conflict=false, conflict_reason="" y conflicting_axes=[].\n\n'
        + _evidence_packet(results, max_chars=7200)
        + '\n\nDevuelve únicamente el objeto estructurado solicitado.'
    )


def _compact_extractor_prompt(comp: Dict[str, Any], year: int, results: List[Dict[str, Any]]) -> str:
    """Prompt mínimo para recuperar fallos transitorios del extractor estructurado."""
    ctype = _text(comp.get('component_type'), 'UNKNOWN').upper()
    facts = comp.get('facts') if isinstance(comp.get('facts'), dict) else {}
    return (
        f'CorePulse extractor de reparación. Año={int(year)}; tipo={ctype}; '
        f'hardware={_text(comp.get("detected_hardware"), "N/A")}; '
        f'facts={json.dumps(facts, ensure_ascii=False, separators=(",", ":"))}.\n'
        f'Ejes: {_axis_definitions(ctype)}\n'
        'Usa EXCLUSIVAMENTE SOURCE/facts. No decidas la clasificación final. '
        'Valores permitidos por eje: WELL_ABOVE, ABOVE, MEETS, SLIGHTLY_BELOW, FAR_BELOW, UNKNOWN. '
        'Si no hay evidencia suficiente, usa UNKNOWN. No infieras datos ausentes.\n'
        'Devuelve SOLO JSON con: primary_position, secondary_position, tertiary_position, '
        'material_limitation (YES/NO/UNKNOWN), evidence_conflict (true/false), conflict_reason, conflicting_axes, basis.\n\n'
        + _evidence_packet(results, max_chars=4300)
    )


def _extract_relevance_axes(*, Groq, api_key: str, available_models: Iterable[str], comp: Dict[str, Any], year: int, results: List[Dict[str, Any]], timeout: float=30.0) -> Dict[str, Any]:
    """el extractor robusto: extracción resistente con schema estricto, segundo modelo y fallback local verificable."""
    available = {str(x) for x in available_models if _text(x)}
    candidates = [m for m in ('openai/gpt-oss-20b', 'openai/gpt-oss-120b') if not available or m in available]
    if not candidates:
        candidates = ['openai/gpt-oss-120b']
    prompt = _extract_axes_prompt(comp, year, results)
    attempts: List[Dict[str, Any]] = []
    last_error = ''
    try:
        client = _new_client(Groq, api_key, timeout)
    except Exception as exc:
        local = _simple_local_axes(comp, results)
        return {'status': 'LOCAL_FALLBACK' if local else 'ERROR', 'model': None, 'axes': local or {}, 'error': _safe_error(exc), 'attempts': []}

    for index, model_id in enumerate(candidates[:2]):
        formats = [
            ('json_schema', {'type': 'json_schema', 'json_schema': {'name': 'corepulse_relevance_axes', 'strict': True, 'schema': _RELEVANCE_EXTRACTOR_SCHEMA}}),
            ('json_object', {'type': 'json_object'}),
        ]
        # El segundo formato solo se usa si el schema no fue soportado o no produjo eje principal.
        for mode_index, (mode, response_format) in enumerate(formats):
            if mode_index == 1 and attempts and attempts[-1].get('status') == 'PARSED_UNKNOWN' and index + 1 < len(candidates):
                # Preferimos probar el segundo modelo antes de gastar otra llamada con el mismo.
                break
            kwargs = {
                'model': model_id,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_completion_tokens': 650,
                'temperature': 0,
                'reasoning_effort': 'low',
                'include_reasoning': False,
                'response_format': response_format,
            }
            try:
                _pace_provider()
                response = client.chat.completions.create(**kwargs)
                message = response.choices[0].message if response and response.choices else None
                content = getattr(message, 'content', '') if message is not None else ''
                parsed = _extract_json_relaxed(content)
                axes = _normalize_axes_payload(parsed) if isinstance(parsed, dict) else _extract_axes_from_text(content)
                if axes and axes.get('primary_position') != 'UNKNOWN':
                    status = 'OK' if isinstance(parsed, dict) else 'REPAIRED_TEXT'
                    attempts.append({'model': model_id, 'mode': mode, 'status': status})
                    return {'status': status, 'model': model_id, 'axes': axes, 'error': None, 'attempts': attempts}
                attempts.append({'model': model_id, 'mode': mode, 'status': 'PARSED_UNKNOWN'})
                last_error = f'{model_id}/{mode} respondió pero primary_position quedó UNKNOWN.'
                # Si el schema respondió un JSON válido pero UNKNOWN, pasa al próximo modelo.
                break
            except Exception as exc:
                code = _error_status_code(exc)
                status = 'RATE_LIMITED' if code == 429 else 'UNSUPPORTED_FORMAT' if code in {400, 404, 405, 422} else 'ERROR'
                attempts.append({'model': model_id, 'mode': mode, 'status': status, 'http_status': code})
                if code == 429:
                    _mark_rate_limited(exc)
                    last_error = _safe_error(exc)
                    break
                last_error = _safe_error(exc)
                if status == 'UNSUPPORTED_FORMAT' and mode == 'json_schema':
                    continue
                break

    # Último intento remoto: contexto reducido y json_object. Se usa solo cuando los
    # extractores anteriores fallaron; no cambia la rúbrica ni inventa ejes.
    compact_candidates = [m for m in ('openai/gpt-oss-120b', 'openai/gpt-oss-20b') if not available or m in available]
    compact_model = compact_candidates[0] if compact_candidates else None
    if compact_model:
        try:
            _pace_provider()
            response = client.chat.completions.create(
                model=compact_model,
                messages=[{'role': 'user', 'content': _compact_extractor_prompt(comp, year, results)}],
                max_completion_tokens=420,
                temperature=0,
                reasoning_effort='low',
                include_reasoning=False,
                response_format={'type': 'json_object'},
            )
            message = response.choices[0].message if response and response.choices else None
            content = getattr(message, 'content', '') if message is not None else ''
            parsed = _extract_json_relaxed(content)
            axes = _normalize_axes_payload(parsed) if isinstance(parsed, dict) else _extract_axes_from_text(content)
            if axes and axes.get('primary_position') != 'UNKNOWN':
                attempts.append({'model': compact_model, 'mode': 'compact_json_repair', 'status': 'REPAIR_OK'})
                return {'status': 'REPAIR_OK', 'model': compact_model, 'axes': axes, 'error': None, 'attempts': attempts}
            attempts.append({'model': compact_model, 'mode': 'compact_json_repair', 'status': 'PARSED_UNKNOWN'})
            last_error = f'{compact_model}/compact_json_repair respondió pero primary_position quedó UNKNOWN.'
        except Exception as exc:
            code = _error_status_code(exc)
            status = 'RATE_LIMITED' if code == 429 else 'ERROR'
            attempts.append({'model': compact_model, 'mode': 'compact_json_repair', 'status': status, 'http_status': code})
            if code == 429:
                _mark_rate_limited(exc)
            last_error = _safe_error(exc)

    local = _simple_local_axes(comp, results)
    if local:
        local = dict(local)
        local.setdefault('conflict_reason', '')
        local.setdefault('conflicting_axes', [])
        return {'status': 'LOCAL_FALLBACK', 'model': None, 'axes': local, 'error': last_error, 'attempts': attempts}
    return {'status': 'ERROR', 'model': None, 'axes': {}, 'error': last_error, 'attempts': attempts}


def _confidence_assessment(profile: Dict[str, Any], axes: Dict[str, Any], classification: str, component_type: str='') -> Dict[str, Any]:
    """Mantiene exactamente los gates de la rúbrica de confianza y añade trazabilidad de conflicto."""
    out = dict(_confidence_assessment_base(profile, axes, classification, component_type))
    if bool(axes.get('evidence_conflict')):
        detail = _sanitize_reason(axes.get('conflict_reason'))
        affected = axes.get('conflicting_axes') if isinstance(axes.get('conflicting_axes'), list) else []
        suffix = ''
        if affected:
            suffix += '; ejes_conflicto=' + ','.join(str(x) for x in affected[:4])
        if detail:
            suffix += '; motivo_conflicto=' + detail[:280]
        out['basis'] = _text(out.get('basis')) + suffix
    return out


def _fixed_reason_base(comp: Dict[str, Any], year: int, classification: str, axes: Dict[str, Any], profile: Dict[str, Any]) -> str:
    name = _text(comp.get('detected_hardware'), 'El componente')
    primary = _text(axes.get('primary_position'), 'UNKNOWN').upper()
    pos = {'WELL_ABOVE': 'claramente por encima', 'ABOVE': 'por encima', 'MEETS': 'en línea con', 'SLIGHTLY_BELOW': 'algo por debajo', 'FAR_BELOW': 'claramente por debajo'}.get(primary, 'sin una posición comparativa suficiente frente a')
    if classification == 'NO_EVALUABLE':
        return f'La evidencia verificada no permitió fijar una posición comparativa suficientemente clara para {name} frente al mainstream {int(year)} de su categoría. CorePulse mantiene NO EVALUABLE en vez de inferir una vigencia.'
    pieces = [f'{name} se clasifica como {classification.replace("_", " ")} para {int(year)} porque la evidencia verificada sitúa su criterio principal {pos} el mainstream actual de su categoría.']
    if _text(axes.get('material_limitation'), 'UNKNOWN').upper() == 'YES':
        pieces.append('La evidencia también señala una limitación material actual.')
    basis = _sanitize_reason(axes.get('basis'))
    if basis:
        pieces.append(f'Base comparativa: {basis}.')
    if bool(axes.get('evidence_conflict')):
        detail = _sanitize_reason(axes.get('conflict_reason'))
        affected = axes.get('conflicting_axes') if isinstance(axes.get('conflicting_axes'), list) else []
        axis_text = ', '.join(str(x).replace('_position', '').replace('_', ' ') for x in affected[:3])
        if detail:
            pieces.append(f'La confianza se reduce porque las fuentes presentan una contradicción material{f" en {axis_text}" if axis_text else ""}: {detail}.')
        else:
            pieces.append(f'La confianza se reduce porque las fuentes presentan una contradicción material{f" en {axis_text}" if axis_text else ""}.')
    pieces.append('La decisión usa la rúbrica determinista de CorePulse y no la antigüedad por sí sola.')
    return ' '.join(pieces)



def _manufacturer_hint(comp: Dict[str, Any]) -> str:
    tokens = component_brand_tokens(comp)
    return ', '.join(tokens[:4]) if tokens else 'fabricante o plataforma detectados'


def _component_search_strategies(comp: Dict[str, Any], year: int) -> List[Dict[str, str]]:
    """Construye búsquedas por tipo de componente sin tablas de fabricantes o modelos."""
    ctype = _text(comp.get('component_type'), 'UNKNOWN').upper()
    name = _text(comp.get('detected_hardware'), 'N/A').split(' · ', 1)[0].strip()
    facts = comp.get('facts') if isinstance(comp.get('facts'), dict) else {}
    manufacturer_hint = _manufacturer_hint(comp)
    common = (
        f'Prioriza documentación oficial del fabricante/plataforma detectados ({manufacturer_hint}) cuando exista, '
        'estándares técnicos aplicables y después varias fuentes técnicas independientes. '
        'Evita marketplaces, foros y páginas SEO. No uses hardware flagship como único estándar mainstream.'
    )
    if ctype == 'RAM':
        try:
            total = int(round(float(facts.get('total_gb'))))
        except Exception:
            total = 0
        speeds = facts.get('configured_speeds_mhz') if isinstance(facts.get('configured_speeds_mhz'), list) else []
        subject = f'{total} GB de RAM' if total > 0 else 'la capacidad de RAM detectada'
        extra = f' Velocidades detectadas: {speeds}.' if speeds else ''
        return [
            {'intent': 'comparison', 'prompt': f'Usa UNA búsqueda web para contextualizar {subject} en PC/notebook mainstream de {int(year)}.{extra} Compara capacidad, margen y requisitos/recomendaciones actuales. {common}'},
            {'intent': 'comparison', 'prompt': f'Búsqueda de rescate: contrasta {subject} con capacidades de memoria mainstream de {int(year)} usando fuentes distintas y buscando evidencia que confirme o contradiga la primera búsqueda. {common}'},
        ]
    category = {'CPU': 'CPU', 'GPU': 'GPU', 'STORAGE': 'unidad de almacenamiento'}.get(ctype, ctype)
    if ctype in {'CPU', 'GPU', 'STORAGE'}:
        axes = {
            'CPU': 'rendimiento single/multi-core, núcleos/hilos y posición práctica',
            'GPU': 'rendimiento gráfico, memoria de vídeo y capacidades actuales',
            'STORAGE': 'interfaz/tecnología, rendimiento práctico y capacidad',
        }[ctype]
        facts_text = json.dumps(facts, ensure_ascii=False, separators=(',', ':'))
        return [
            {'intent': 'comparison', 'prompt': f'Usa UNA búsqueda web para situar el {category} exacto "{name}" frente al mainstream de su misma categoría en {int(year)}. Hechos reales detectados: {facts_text}. Necesito identidad/especificaciones verificables y comparación actual sobre {axes}. {common}'},
            {'intent': 'comparison', 'prompt': f'Búsqueda de rescate independiente para "{name}": usa dominios distintos, verifica el modelo exacto y busca evidencia que confirme o contradiga su posición frente al mainstream {int(year)} sobre {axes}. {common}'},
        ]
    return [{'intent': 'comparison', 'prompt': f'Investiga el hardware exacto "{name}" y su posición mainstream en {int(year)} sin inferir datos ausentes. {common}'}]


def _merge_results(*groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Da prioridad a autoridad, calidad y coincidencia exacta sin inventar ni alterar snippets."""
    merged = _merge_results_base(*groups)
    def rank(item: Dict[str, Any]) -> tuple:
        tier = _text(item.get('quality_tier'), 'C')
        tier_score = {'A': 3, 'B': 2, 'C': 1}.get(tier, 0)
        role = _text(item.get('role'))
        role_score = 2 if role == 'both' else 1 if role in {'component', 'context'} else 0
        try:
            provider_score = float(item.get('score') or 0.0)
        except Exception:
            provider_score = 0.0
        return (tier_score, role_score, int(item.get('quality_points') or 0), provider_score)
    return sorted(merged, key=rank, reverse=True)[:10]


try:
    __all__ = list(dict.fromkeys(list(__all__) + [
        '_extract_json_relaxed', '_normalize_axes_payload', '_extract_axes_from_text',
        '_RELEVANCE_ROUTE_ID'
    ]))
except Exception:
    pass

# ---------------------------------------------------------------------------
# la estabilización anual · Stable Relevance Category
# - La IA/web solo extrae evidencia/ejes; la categoría final queda en una
#   rúbrica determinista con guardas objetivas para extremos.
# - OPTIMO exige superioridad clara + evidencia fuerte; una sola extracción
#   optimista no puede elevar hardware a OPTIMO con evidencia media/baja.
# - Entre reevaluaciones del mismo año, un cambio >1 categoría requiere
#   confianza ALTA y evidencia coherente. Se conserva trazabilidad del ajuste.
# ---------------------------------------------------------------------------
_RELEVANCE_CACHE_SCHEMA = 5
_CACHE_SCHEMA = _RELEVANCE_CACHE_SCHEMA
_RELEVANCE_ROUTE_ID = 'universal_per_component_relevance'
_RELEVANCE_DECISION_METHOD = 'COREPULSE_DETERMINISTIC_RUBRIC_V4_STABLE_CATEGORY'
_RELEVANCE_CLASS_ORDER = {
    'POR_DEBAJO_DEL_ESTANDAR': 0,
    'JUSTO': 1,
    'ESTANDAR': 2,
    'OPTIMO': 3,
}


def _stability_profile_strong_for_optimal(profile: Dict[str, Any]) -> bool:
    """Gate de evidencia para OPTIMO; no depende de cantidad bruta únicamente."""
    if not isinstance(profile, dict) or not bool(profile.get('sufficient')):
        return False
    tiers = profile.get('tier_counts') if isinstance(profile.get('tier_counts'), dict) else {}
    a_count = int(tiers.get('A') or 0)
    b_count = int(tiers.get('B') or 0)
    return (
        int(profile.get('source_count') or 0) >= 6
        and int(profile.get('independent_hosts') or 0) >= 3
        and int(profile.get('strong_hosts') or 0) >= 2
        and int(profile.get('quality_points') or 0) >= 8
        and (a_count >= 1 or b_count >= 3)
    )


def _deterministic_relevance_decision(ctype: str, axes: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Decide vigencia con ancla en el eje principal y guardas para extremos.

    La puntuación ponderada sigue aportando granularidad, pero OPTIMO y
    POR_DEBAJO_DEL_ESTANDAR requieren evidencia explícita acorde a su severidad.
    """
    ctype = _text(ctype, 'UNKNOWN').upper()
    axes = axes if isinstance(axes, dict) else {}
    weights = _CATEGORY_WEIGHTS.get(ctype, (0.65, 0.22, 0.13))
    positions = [_text(axes.get(k), 'UNKNOWN').upper() for k in ('primary_position', 'secondary_position', 'tertiary_position')]
    primary = positions[0]
    if primary == 'UNKNOWN':
        return {'classification': 'NO_EVALUABLE', 'raw_classification': 'NO_EVALUABLE', 'score': None, 'known_axes': 0, 'category_guard': 'PRIMARY_UNKNOWN'}

    weighted = total_w = 0.0
    known = 0
    for pos, weight in zip(positions, weights):
        value = _POSITION_SCORE.get(pos)
        if value is None:
            continue
        weighted += float(value) * float(weight)
        total_w += float(weight)
        known += 1
    if total_w <= 0:
        return {'classification': 'NO_EVALUABLE', 'raw_classification': 'NO_EVALUABLE', 'score': None, 'known_axes': 0, 'category_guard': 'NO_KNOWN_AXES'}

    score = weighted / total_w
    material = _text(axes.get('material_limitation'), 'UNKNOWN').upper()
    conflict = bool(axes.get('evidence_conflict'))
    if material == 'YES':
        score -= 0.3

    if score >= 1.1:
        raw_cls = 'OPTIMO'
    elif score >= -0.35:
        raw_cls = 'ESTANDAR'
    elif score >= -1.15:
        raw_cls = 'JUSTO'
    else:
        raw_cls = 'POR_DEBAJO_DEL_ESTANDAR'

    final_cls = raw_cls
    guard = 'NONE'

    # El criterio principal gobierna los extremos. Un componente que solo
    # "cumple" mainstream no puede ser OPTIMO por ejes secundarios ruidosos.
    if primary == 'FAR_BELOW':
        final_cls = 'POR_DEBAJO_DEL_ESTANDAR'
        guard = 'PRIMARY_FAR_BELOW'
    elif primary == 'SLIGHTLY_BELOW' and final_cls in {'OPTIMO', 'ESTANDAR'}:
        final_cls = 'JUSTO'
        guard = 'PRIMARY_SLIGHTLY_BELOW'
    elif primary == 'MEETS' and final_cls == 'OPTIMO':
        final_cls = 'ESTANDAR'
        guard = 'PRIMARY_ONLY_MEETS'
    elif primary == 'ABOVE' and final_cls == 'OPTIMO':
        # ABOVE significa por encima, pero OPTIMO queda reservado para una
        # superioridad clara (WELL_ABOVE) y corroborada.
        final_cls = 'ESTANDAR'
        guard = 'OPTIMAL_REQUIRES_WELL_ABOVE'

    if final_cls == 'OPTIMO':
        secondary_positive = any(p in {'ABOVE', 'WELL_ABOVE'} for p in positions[1:] if p != 'UNKNOWN')
        no_negative_axis = all(p not in {'SLIGHTLY_BELOW', 'FAR_BELOW'} for p in positions if p != 'UNKNOWN')
        strong_gate = (
            primary == 'WELL_ABOVE'
            and known >= 2
            and secondary_positive
            and no_negative_axis
            and material != 'YES'
            and not conflict
            and _stability_profile_strong_for_optimal(profile or {})
        )
        if not strong_gate:
            final_cls = 'ESTANDAR'
            guard = 'OPTIMAL_EVIDENCE_GATE'

    # La categoría más negativa también exige un ancla negativa clara; evita
    # que un eje secundario aislado derribe dos niveles al componente.
    if final_cls == 'POR_DEBAJO_DEL_ESTANDAR' and primary != 'FAR_BELOW':
        negatives = [p for p in positions if p in {'SLIGHTLY_BELOW', 'FAR_BELOW'}]
        severe = any(p == 'FAR_BELOW' for p in positions[1:])
        if not (primary == 'SLIGHTLY_BELOW' and severe and len(negatives) >= 2):
            final_cls = 'JUSTO'
            guard = 'SEVERE_NEGATIVE_EVIDENCE_GATE'

    # Una limitación material comprobada impide OPTIMO, pero no se convierte
    # automáticamente en un diagnóstico de salud ni obliga a una clase baja.
    if material == 'YES' and final_cls == 'OPTIMO':
        final_cls = 'ESTANDAR'
        guard = 'MATERIAL_LIMITATION_CEILING'

    return {
        'classification': final_cls,
        'raw_classification': raw_cls,
        'score': round(score, 3),
        'known_axes': known,
        'category_guard': guard,
    }



def _fixed_reason(comp: Dict[str, Any], year: int, classification: str, axes: Dict[str, Any], profile: Dict[str, Any]) -> str:
    base = _fixed_reason_base(comp, year, classification, axes, profile)
    if isinstance(axes, dict) and bool(axes.get('_category_guard_applied')):
        raw_cls = _text(axes.get('_raw_classification')).upper()
        guard = _text(axes.get('_category_guard'))
        if raw_cls and raw_cls != _text(classification).upper():
            base += (
                f' La puntuación bruta sugería {raw_cls.replace("_", " ")}, pero CorePulse aplicó la guarda '
                f'determinista {guard}: las categorías extremas requieren evidencia comparativa más fuerte y coherente.'
            )
    return base


def _classify_from_verified_evidence(*, Groq, api_key: str, available_models: Iterable[str], comp: Dict[str, Any], year: int, results: List[Dict[str, Any]], timeout: float=30.0) -> Dict[str, Any]:
    profile = _evidence_profile(comp, results)
    if not profile.get('sufficient'):
        return {
            'status': 'OK', 'model': None, 'classification': 'NO_EVALUABLE', 'confidence': 'BAJA',
            'reason': 'La evidencia verificada aún no cubre el componente y su contexto mainstream con suficiente calidad.',
            'decision_method': _RELEVANCE_DECISION_METHOD, 'decision_score': None, 'evidence_axes': {},
        }
    extracted = _extract_relevance_axes(
        Groq=Groq, api_key=api_key, available_models=available_models,
        comp=comp, year=year, results=results, timeout=timeout,
    )
    axes = dict(extracted.get('axes')) if isinstance(extracted.get('axes'), dict) else {}
    decision = _deterministic_relevance_decision(_text(comp.get('component_type'), 'UNKNOWN'), axes, profile)
    cls = _text(decision.get('classification'), 'NO_EVALUABLE').upper()
    raw_cls = _text(decision.get('raw_classification'), cls).upper()
    guard = _text(decision.get('category_guard'), 'NONE')
    axes['_raw_classification'] = raw_cls
    axes['_category_guard'] = guard
    axes['_category_guard_applied'] = bool(raw_cls != cls)

    confidence_eval = _confidence_assessment(profile, axes, cls, _text(comp.get('component_type'), 'UNKNOWN'))
    conf = _text(confidence_eval.get('confidence'), 'BAJA').upper()
    if extracted.get('status') == 'LOCAL_FALLBACK' and conf == 'ALTA':
        conf = 'MEDIA'
    reason = _fixed_reason(comp, year, cls, axes, profile)
    return {
        'status': 'OK',
        'model': _text(extracted.get('model')) or None,
        'extractor_model': _text(extracted.get('model')) or None,
        'reason_model': None,
        'classification': cls,
        'raw_classification': raw_cls,
        'category_guard': guard,
        'confidence': conf,
        'confidence_score': confidence_eval.get('score'),
        'confidence_basis': confidence_eval.get('basis'),
        'reason': reason,
        'decision_method': _RELEVANCE_DECISION_METHOD,
        'decision_score': decision.get('score'),
        'known_axes': decision.get('known_axes'),
        'evidence_axes': axes,
        'extraction_status': extracted.get('status'),
        'extraction_error': extracted.get('error'),
        'extraction_attempts': list(extracted.get('attempts') or []),
    }


def _stability_read_cache_file() -> Dict[str, Any]:
    path = _cache_path()
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _load_cache() -> Dict[str, Any]:
    """Esquema actual: invalida resultados el extractor robusto como hit, pero los conserva como referencia temporal."""
    obj = _stability_read_cache_file()
    schema = int(obj.get('schema') or 0) if isinstance(obj, dict) else 0
    entries = obj.get('entries') if isinstance(obj.get('entries'), dict) else {}
    if schema == _RELEVANCE_CACHE_SCHEMA:
        refs = obj.get('stability_reference') if isinstance(obj.get('stability_reference'), dict) else {}
        return {'schema': _RELEVANCE_CACHE_SCHEMA, 'entries': entries, 'stability_reference': refs}
    if schema in {3, 4} and entries:
        # Las evaluaciones anteriores se conservan solo como referencia de estabilidad.
        # La arquitectura universal vuelve a investigar para aplicar sus reglas actuales.
        return {'schema': _RELEVANCE_CACHE_SCHEMA, 'entries': {}, 'stability_reference': entries, 'migrated_from_schema': schema}
    return {'schema': _RELEVANCE_CACHE_SCHEMA, 'entries': {}, 'stability_reference': {}}


def _stability_reference_entry(cache: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    current = (cache.get('entries') or {}).get(key)
    legacy = (cache.get('stability_reference') or {}).get(key)
    candidate = current if isinstance(current, dict) else legacy if isinstance(legacy, dict) else None
    if not isinstance(candidate, dict):
        return None
    age = _cache_age_days(candidate)
    max_age = _env_float('COREPULSE_AI_STABILITY_REFERENCE_DAYS', 45.0, 1.0, 180.0)
    if age is None or age > max_age:
        return None
    return candidate


def _recover_failed_live_rows(cache: Dict[str, Any], components: List[Dict[str, Any]], live_rows: Dict[str, Dict[str, Any]], year: int) -> int:
    """Recupera fallos transitorios usando solo una referencia exacta verificada.

    La clave de caché incluye año, tipo, identidad y hechos estables. Por ello una
    evaluación de otra GPU/unidad o de otro hardware no puede heredarse. La recuperación
    nunca aumenta confianza y no se guarda como una nueva evaluación verificada.
    """
    comp_by_id = {
        _text(c.get('id') or c.get('component_id')): c
        for c in components or [] if isinstance(c, dict) and _text(c.get('id') or c.get('component_id'))
    }
    recovered = 0
    for cid, failed in list(live_rows.items()):
        comp = comp_by_id.get(cid)
        if not isinstance(comp, dict) or not isinstance(failed, dict):
            continue
        cls = _text(failed.get('classification')).upper()
        extraction_status = _text(failed.get('extraction_status')).upper()
        research_status = _text(failed.get('research_status')).upper()
        if not (
            cls == 'NO_EVALUABLE'
            and research_status == 'INSUFFICIENT_COMPARATIVE_CONTEXT'
            and extraction_status in {'ERROR', 'RATE_LIMITED', 'PARSED_UNKNOWN', ''}
            and int(failed.get('source_count') or 0) >= 2
        ):
            continue
        entry = _stability_reference_entry(cache, _cache_key(comp, year))
        if not isinstance(entry, dict):
            continue
        reference = entry.get('row') if isinstance(entry.get('row'), dict) else None
        if not isinstance(reference, dict):
            continue
        ref_cls = _text(reference.get('classification')).upper()
        ref_status = _text(reference.get('research_status'), 'OK').upper()
        ref_axes = reference.get('evidence_axes') if isinstance(reference.get('evidence_axes'), dict) else {}
        if ref_cls not in _RELEVANCE_CLASS_ORDER or ref_status not in {'OK', 'CACHE_VERIFIED', 'RECOVERED_VERIFIED_REFERENCE'}:
            continue
        if int(reference.get('source_count') or 0) < 2:
            continue
        if _text(ref_axes.get('primary_position'), 'UNKNOWN').upper() == 'UNKNOWN' and reference.get('decision_score') is None:
            continue

        row = dict(reference)
        if _text(row.get('confidence'), 'BAJA').upper() == 'ALTA':
            row['confidence'] = 'MEDIA'
        row['component_id'] = cid
        row['component_type'] = _text(failed.get('component_type') or reference.get('component_type')).upper()
        row['detected_hardware'] = _text(failed.get('detected_hardware') or reference.get('detected_hardware'))
        row['research_status'] = 'RECOVERED_VERIFIED_REFERENCE'
        row['cache_hit'] = False
        row['reference_recovery'] = True
        row['reference_age_days'] = _cache_age_days(entry)
        row['current_extraction_status'] = failed.get('extraction_status')
        row['current_extraction_error'] = failed.get('extraction_error')
        row['current_extraction_attempts'] = list(failed.get('extraction_attempts') or [])
        row['extraction_status'] = 'REFERENCE_FALLBACK'
        row['current_search_source_count'] = int(failed.get('source_count') or 0)
        age = row.get('reference_age_days')
        age_text = 'reciente' if age is None else f'de hace {float(age):.1f} días'
        row['reason'] = (
            f'{row["detected_hardware"]} conserva temporalmente la clasificación {ref_cls.replace("_", " ")} para {int(year)} '
            f'usando una evaluación verificada {age_text}. La búsqueda actual obtuvo evidencia, pero el extractor falló de forma '
            'transitoria; CorePulse no convierte ese fallo de formato en una categoría nueva. La confianza se limita como máximo a MEDIA.'
        )
        live_rows[cid] = row
        recovered += 1
    return recovered


def _stability_stabilize_row(row: Dict[str, Any], prior_row: Dict[str, Any], *, year: int, prior_age_days: Optional[float]) -> bool:
    """Limita saltos >1 categoría dentro del mismo año salvo evidencia ALTA y coherente."""
    if not isinstance(row, dict) or not isinstance(prior_row, dict):
        return False
    new_cls = _text(row.get('classification')).upper()
    prior_cls = _text(prior_row.get('classification')).upper()
    if new_cls not in _RELEVANCE_CLASS_ORDER or prior_cls not in _RELEVANCE_CLASS_ORDER:
        return False
    prior_conf = _text(prior_row.get('confidence'), 'BAJA').upper()
    if prior_conf not in {'MEDIA', 'ALTA'}:
        return False
    delta = _RELEVANCE_CLASS_ORDER[new_cls] - _RELEVANCE_CLASS_ORDER[prior_cls]
    if abs(delta) <= 1:
        return False

    axes = row.get('evidence_axes') if isinstance(row.get('evidence_axes'), dict) else {}
    current_conf = _text(row.get('confidence'), 'BAJA').upper()
    current_score = int(row.get('confidence_score') or 0) if str(row.get('confidence_score') or '').strip() else 0
    strong_override = (
        current_conf == 'ALTA'
        and current_score >= 8
        and not bool(axes.get('evidence_conflict'))
        and sum(1 for k in ('primary_position', 'secondary_position', 'tertiary_position') if _text(axes.get(k), 'UNKNOWN').upper() != 'UNKNOWN') >= 2
    )
    if strong_override:
        return False

    target_idx = _RELEVANCE_CLASS_ORDER[prior_cls] + (1 if delta > 0 else -1)
    inverse = {v: k for k, v in _RELEVANCE_CLASS_ORDER.items()}
    target_cls = inverse[target_idx]
    raw_new = new_cls
    row['raw_classification'] = raw_new
    row['classification'] = target_cls
    row['stability_guard_applied'] = True
    row['stability_reference_classification'] = prior_cls
    row['stability_reference_age_days'] = None if prior_age_days is None else round(float(prior_age_days), 3)
    row['stability_reason'] = (
        f'La nueva investigación proponía {raw_new}, pero el cambio supera una categoría respecto de la referencia '
        f'verificada previa ({prior_cls}) y no alcanzó evidencia ALTA suficiente para justificar el salto completo.'
    )
    if _text(row.get('confidence')).upper() == 'ALTA':
        row['confidence'] = 'MEDIA'
    row['decision_method'] = _RELEVANCE_DECISION_METHOD
    row_axes = dict(axes)
    row_axes['_stability_guard_applied'] = True
    row_axes['_stability_reference_classification'] = prior_cls
    row_axes['_stability_raw_classification'] = raw_new
    row['evidence_axes'] = row_axes
    name = _text(row.get('detected_hardware'), 'El componente')
    row['reason'] = (
        f'{name} se clasifica como {target_cls.replace("_", " ")} para {int(year)}. '
        f'La investigación nueva sugería {raw_new.replace("_", " ")}, pero CorePulse limita cambios de más de una '
        f'categoría dentro del mismo año cuando la evidencia nueva no alcanza confianza ALTA. '
        f'La referencia previa verificada era {prior_cls.replace("_", " ")}; el ajuste conserva trazabilidad y evita oscilaciones por variaciones de búsqueda.'
    )
    return True


def _cache_row(cache: Dict[str, Any], comp: Dict[str, Any], year: int, row: Dict[str, Any]) -> bool:
    if _text(row.get('classification')).upper() == 'NO_EVALUABLE':
        return False
    if _text(row.get('research_status')).upper() not in {'OK', 'CACHE_VERIFIED'}:
        return False
    key = _cache_key(comp, year)
    prior_entry = _stability_reference_entry(cache, key)
    if isinstance(prior_entry, dict):
        prior_row = prior_entry.get('row') if isinstance(prior_entry.get('row'), dict) else None
        if isinstance(prior_row, dict):
            _stability_stabilize_row(row, prior_row, year=year, prior_age_days=_cache_age_days(prior_entry))

    safe_row = dict(row)
    safe_row.pop('search_rounds', None)
    safe_row.pop('cache_hit', None)
    safe_row.pop('cache_age_days', None)
    cache.setdefault('entries', {})[key] = {
        'saved_at_utc': _datetime.now(_timezone.utc).isoformat().replace('+00:00', 'Z'),
        'year': int(year),
        'component_type': _text(comp.get('type') or comp.get('component_type')).upper(),
        'detected_hardware': _text(comp.get('name') or comp.get('detected_hardware')),
        'stable_facts': _stable_facts(comp),
        'row': safe_row,
    }
    return True


try:
    __all__ = list(dict.fromkeys(list(__all__) + [
        '_RELEVANCE_CACHE_SCHEMA', '_RELEVANCE_ROUTE_ID', '_RELEVANCE_DECISION_METHOD',
        '_stability_profile_strong_for_optimal', '_stability_stabilize_row'
    ]))
except Exception:
    pass
