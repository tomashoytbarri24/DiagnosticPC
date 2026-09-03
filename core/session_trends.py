"""Recopila y analiza tendencias de diagnósticos realizados durante la sesión actual."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import copy, json, os, threading, time, uuid
from pathlib import Path
from core.hardware_policy import select_representative_gpu_stats
SCHEMA_VERSION = 4
MAX_SESSION_TRENDS = 10

def _num(value):
    return isinstance(value, (int, float)) and (not isinstance(value, bool))

def _default_path():
    root = Path(__file__).resolve().parents[1]
    data = root / 'data'
    data.mkdir(parents=True, exist_ok=True)
    return data / 'session_trends.json'

def build_session_alert_summary(state):
    state = state or {}
    alerts = state.get('alerts') or {}
    episodes = {}
    for status, items in (('ACTIVE', alerts.get('active') or []), ('RESOLVED', alerts.get('history') or [])):
        for item in items:
            if not isinstance(item, dict):
                continue
            ident = (str(item.get('key') or ''), round(float(item.get('first_seen') or 0), 3))
            candidate = dict(item)
            candidate['_status'] = status
            if ident not in episodes or status == 'ACTIVE':
                episodes[ident] = candidate
    events = list(episodes.values())[-MAX_SESSION_TRENDS:]
    return {'active': sum((1 for x in events if x.get('_status') == 'ACTIVE')), 'resolved': sum((1 for x in events if x.get('_status') == 'RESOLVED')), 'critical': sum((1 for x in events if x.get('level') == 'CRITICAL')), 'warning': sum((1 for x in events if x.get('level') == 'WARNING')), 'info': sum((1 for x in events if x.get('level') == 'INFO')), 'event_count': len(events), 'source': 'CURRENT_AGENT_SESSION'}

def classify_session_profile(session):
    if not isinstance(session, dict):
        return 'LEGACY'
    profile = str(session.get('profile') or '').upper()
    if profile in {'GAME', 'DESKTOP'}:
        return profile
    context = str(session.get('final_context') or session.get('context') or '').upper()
    if context.startswith('GAME'):
        return 'GAME'
    if session.get('schema_version') in {2, 3, 4}:
        return 'DESKTOP'
    return 'LEGACY'

def _stat(stats, section, key, field):
    try:
        value = ((stats.get(section) or {}).get(key) or {}).get(field)
        return float(value) if _num(value) else None
    except Exception:
        return None

def _representative_gpu_stats(stats):
    """Obtiene la GPU representativa por actividad real, nunca por orden o fabricante."""
    gpus = (stats or {}).get('gpus') or {}
    _name, selected = select_representative_gpu_stats(gpus if isinstance(gpus, dict) else {})
    return selected


class SessionTrendCollector:
    """Clase responsable de `SessionTrendCollector` dentro de CorePulse. Conserva los contratos de integridad del módulo."""

    def __init__(self, path=None, max_sessions=MAX_SESSION_TRENDS):
        self.path = Path(path) if path else _default_path()
        self.max_sessions = min(MAX_SESSION_TRENDS, max(1, int(max_sessions)))
        self.lock = threading.RLock()
        self.runtime_session_id = str(uuid.uuid4())
        self.started_at = time.time()
        self.sample_count = 0
        self._last_state = {}
        self._finalized = False
        self._save({'schema_version': SCHEMA_VERSION, 'runtime_session_id': self.runtime_session_id, 'sessions': []})

    def add_sample(self, telemetry, state=None):
        if isinstance(telemetry, dict):
            self.sample_count += 1
        if isinstance(state, dict):
            self._last_state = copy.deepcopy(state)

    def _load(self):
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
            if not isinstance(raw, dict) or raw.get('runtime_session_id') != self.runtime_session_id:
                return {'schema_version': SCHEMA_VERSION, 'runtime_session_id': self.runtime_session_id, 'sessions': []}
            raw.setdefault('sessions', [])
            if not isinstance(raw['sessions'], list):
                raw['sessions'] = []
            return raw
        except Exception:
            return {'schema_version': SCHEMA_VERSION, 'runtime_session_id': self.runtime_session_id, 'sessions': []}

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + '.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, self.path)

    def record_diagnostic(self, diagnostic_result, state=None):
        if not isinstance(diagnostic_result, dict):
            return None
        state = state or self._last_state or {}
        stats = diagnostic_result.get('statistics') or {}
        gpu = _representative_gpu_stats(stats)
        context = str(state.get('context') or state.get('mode') or 'DESKTOP').upper()
        profile = 'GAME' if context.startswith('GAME') or str(state.get('mode') or '').upper() == 'GAME' else 'DESKTOP'
        alerts = build_session_alert_summary(state)
        now = time.time()
        record = {'schema_version': SCHEMA_VERSION, 'runtime_session_id': self.runtime_session_id, 'session_id': str(uuid.uuid4()), 'started_at': now - float(diagnostic_result.get('duration_seconds') or 0), 'ended_at': now, 'duration_seconds': float(diagnostic_result.get('duration_seconds') or 0), 'sample_count': int(diagnostic_result.get('sample_count') or 0), 'profile': profile, 'accuracy': 'DIAGNOSTIC_CERTIFIED', 'final_context': context, 'principal_game': (state.get('game') or {}).get('name') if isinstance(state.get('game'), dict) else None, 'total_game_seconds': float(diagnostic_result.get('duration_seconds') or 0) if profile == 'GAME' else 0.0, 'game_active_seconds': float(diagnostic_result.get('duration_seconds') or 0) if profile == 'GAME' else 0.0, 'averages': {'cpu_usage': _stat(stats, 'cpu', 'usage_percent', 'avg'), 'cpu_temp': _stat(stats, 'cpu', 'package_temp_c', 'avg'), 'ram_usage': _stat(stats, 'ram', 'usage_percent', 'avg'), 'gpu_usage': (gpu.get('usage_percent') or {}).get('avg') if isinstance(gpu.get('usage_percent'), dict) else None, 'gpu_temp': (gpu.get('temperature_c') or {}).get('avg') if isinstance(gpu.get('temperature_c'), dict) else None}, 'maxima': {'cpu_usage': _stat(stats, 'cpu', 'usage_percent', 'max'), 'cpu_temp': _stat(stats, 'cpu', 'package_temp_c', 'max'), 'ram_usage': _stat(stats, 'ram', 'usage_percent', 'max'), 'gpu_usage': (gpu.get('usage_percent') or {}).get('max') if isinstance(gpu.get('usage_percent'), dict) else None, 'gpu_temp': (gpu.get('temperature_c') or {}).get('max') if isinstance(gpu.get('temperature_c'), dict) else None}, 'game_averages': {}, 'game_maxima': {}, 'alerts': {**alerts, 'source': 'CURRENT_AGENT_SESSION'}, 'alerts_trusted': True, 'overall': diagnostic_result.get('overall_status') or state.get('overall') or 'UNKNOWN'}
        if profile == 'GAME':
            record['game_averages'] = copy.deepcopy(record['averages'])
            record['game_maxima'] = copy.deepcopy(record['maxima'])
        with self.lock:
            data = self._load()
            data['sessions'].append(record)
            data['sessions'] = data['sessions'][-self.max_sessions:]
            self._save(data)
        return copy.deepcopy(record)

    def snapshot(self, alert_summary=None, state=None):
        sessions = self.load_sessions(limit=1)
        return sessions[0] if sessions else None

    def finalize(self, alert_summary=None, state=None):
        sessions = self.load_sessions(limit=1)
        return sessions[0] if sessions else None

    def load_sessions(self, limit=MAX_SESSION_TRENDS):
        data = self._load()
        sessions = copy.deepcopy(data.get('sessions') or [])
        for session in sessions:
            session['profile'] = classify_session_profile(session)
            session['alerts_trusted'] = (session.get('alerts') or {}).get('source') == 'CURRENT_AGENT_SESSION'
        sessions.sort(key=lambda item: -float(item.get('ended_at') or 0) if _num(item.get('ended_at')) else 0)
        return sessions[:min(self.max_sessions, max(1, int(limit)))]

    def clear_session(self):
        with self.lock:
            for p in (self.path, self.path.with_suffix(self.path.suffix + '.tmp')):
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass

class SessionTrendAnalyzer:

    def __init__(self, sessions):
        self.sessions = list(sessions or [])

    @staticmethod
    def _value(session, section, key):
        value = (session.get(section) or {}).get(key)
        return float(value) if _num(value) else None

    @staticmethod
    def _direction(new, old):
        if new is None or old is None:
            return {'status': 'INSUFFICIENT', 'delta': None}
        delta = round(new - old, 2)
        if abs(delta) < 1.0:
            status = 'STABLE'
        elif delta < 0:
            status = 'IMPROVING'
        else:
            status = 'WORSENING'
        return {'status': status, 'delta': delta}

    @staticmethod
    def _comparison_scope(session):
        return classify_session_profile(session)

    def _find_comparable_previous(self, sessions):
        if not sessions:
            return None
        newest = sessions[0]
        scope = self._comparison_scope(newest)
        if scope == 'LEGACY':
            return None
        for candidate in sessions[1:]:
            if self._comparison_scope(candidate) == scope:
                return candidate
        return None

    def summary(self, limit=10):
        sessions = self.sessions[:limit]
        if not sessions:
            return {'session_count': 0, 'validated_sessions': 0, 'legacy_sessions': 0, 'warning_sessions': 0, 'critical_sessions': 0, 'warning_events': 0, 'critical_events': 0, 'cpu_max_average': None, 'gpu_max_average': None, 'summary_cpu_value': None, 'summary_gpu_value': None, 'summary_profile': None, 'summary_basis': None, 'cpu_comparison': {'status': 'NO_DATA', 'delta': None}, 'gpu_comparison': {'status': 'NO_DATA', 'delta': None}, 'comparison_profile': None, 'game_sessions': 0}
        validated = [session for session in sessions if classify_session_profile(session) != 'LEGACY']
        trusted_alert_sessions = [session for session in validated if session.get('alerts_trusted', False)]
        cpu_values = [self._value(session, 'maxima', 'cpu_temp') for session in validated]
        cpu_values = [value for value in cpu_values if value is not None]
        gpu_values = [self._value(session, 'maxima', 'gpu_temp') for session in validated]
        gpu_values = [value for value in gpu_values if value is not None]

        def average(values):
            return round(sum(values) / len(values), 2) if values else None
        newest = sessions[0]
        newest_profile = self._comparison_scope(newest)
        previous = self._find_comparable_previous(sessions)
        if newest_profile == 'LEGACY' or previous is None:
            cpu_comparison = {'status': 'NOT_COMPARABLE', 'delta': None}
            gpu_comparison = {'status': 'NOT_COMPARABLE', 'delta': None}
        else:
            comparison_section = 'game_maxima' if newest_profile == 'GAME' else 'maxima'
            cpu_comparison = self._direction(self._value(newest, comparison_section, 'cpu_temp'), self._value(previous, comparison_section, 'cpu_temp'))
            gpu_comparison = self._direction(self._value(newest, comparison_section, 'gpu_temp'), self._value(previous, comparison_section, 'gpu_temp'))
        summary_section = 'game_maxima' if newest_profile == 'GAME' else 'maxima'
        summary_cpu_value = self._value(newest, summary_section, 'cpu_temp') if newest_profile != 'LEGACY' else None
        summary_gpu_value = self._value(newest, summary_section, 'gpu_temp') if newest_profile != 'LEGACY' else None
        return {'session_count': len(sessions), 'validated_sessions': len(validated), 'legacy_sessions': len(sessions) - len(validated), 'warning_sessions': sum((1 for session in trusted_alert_sessions if (session.get('alerts') or {}).get('warning', 0) > 0)), 'critical_sessions': sum((1 for session in trusted_alert_sessions if (session.get('alerts') or {}).get('critical', 0) > 0)), 'warning_events': sum((int((session.get('alerts') or {}).get('warning', 0) or 0) for session in trusted_alert_sessions)), 'critical_events': sum((int((session.get('alerts') or {}).get('critical', 0) or 0) for session in trusted_alert_sessions)), 'cpu_max_average': average(cpu_values), 'gpu_max_average': average(gpu_values), 'summary_cpu_value': summary_cpu_value, 'summary_gpu_value': summary_gpu_value, 'summary_profile': newest_profile if newest_profile != 'LEGACY' else None, 'summary_basis': ('GAME_ACTIVE' if newest_profile == 'GAME' else 'FULL_SESSION') if newest_profile != 'LEGACY' else None, 'cpu_comparison': cpu_comparison, 'gpu_comparison': gpu_comparison, 'comparison_profile': newest_profile if newest_profile != 'LEGACY' else None, 'comparison_basis': ('GAME_ACTIVE' if newest_profile == 'GAME' else 'FULL_SESSION') if newest_profile != 'LEGACY' else None, 'game_sessions': sum((1 for session in validated if classify_session_profile(session) == 'GAME'))}
