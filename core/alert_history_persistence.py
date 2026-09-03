"""Gestiona la persistencia temporal de episodios de alertas de la ejecución actual."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import copy, json, os, threading, time, uuid
from pathlib import Path
SCHEMA_VERSION = 2
MAX_EVENTS = 10

def _default_path():
    root = Path(__file__).resolve().parents[1]
    data = root / 'data'
    data.mkdir(parents=True, exist_ok=True)
    return data / 'alert_history.json'

class PersistentAlertHistory:
    """Clase responsable de `PersistentAlertHistory` dentro de CorePulse. Conserva los contratos de integridad del módulo."""

    def __init__(self, path=None, max_events=MAX_EVENTS):
        self.path = Path(path) if path else _default_path()
        self.max_events = min(10, max(1, int(max_events)))
        self.lock = threading.RLock()
        self.session_id = str(uuid.uuid4())
        self.session_started_at = time.time()
        self._data = self._empty()
        self._atomic_save()

    def _empty(self):
        return {'schema_version': SCHEMA_VERSION, 'runtime_session_id': self.session_id, 'events': []}

    def _atomic_save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + '.tmp')
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, self.path)

    @staticmethod
    def _identity(event):
        return (str(event.get('key') or ''), round(float(event.get('first_seen') or 0), 3))

    @staticmethod
    def _activity(event):
        return float(event.get('last_seen') or event.get('resolved_at') or event.get('first_seen') or 0)

    def sync_rows(self, rows):
        now = time.time()
        with self.lock:
            existing = {self._identity(x): x for x in self._data['events'] if isinstance(x, dict)}
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                event = copy.deepcopy(row)
                event['session_id'] = self.session_id
                event['persisted_at'] = now
                ident = self._identity(event)
                if ident in existing:
                    existing[ident].update(event)
                else:
                    self._data['events'].append(event)
                    existing[ident] = event
            self._data['events'].sort(key=self._activity)
            self._data['events'] = self._data['events'][-self.max_events:]
            self._atomic_save()

    def get_events(self, limit=10):
        with self.lock:
            events = copy.deepcopy(self._data['events'])
        events.sort(key=self._activity, reverse=True)
        return events[:min(self.max_events, max(1, int(limit)))]

    def build_session_summary(self, state=None, ended_at=None):
        events = self.get_events(limit=self.max_events)
        counts = {'CRITICAL': 0, 'WARNING': 0, 'INFO': 0}
        components = {}
        for event in events:
            level = str(event.get('level') or '').upper()
            comp = event.get('component', 'SYSTEM')
            if level in counts:
                counts[level] += 1
            components[comp] = components.get(comp, 0) + 1
        overall = 'CRITICAL' if counts['CRITICAL'] else 'WARNING' if counts['WARNING'] else 'INFO' if counts['INFO'] else 'NORMAL'
        return {'session_id': self.session_id, 'started_at': self.session_started_at, 'ended_at': ended_at or time.time(), 'overall': overall, 'event_count': len(events), 'severity_counts': counts, 'components': components, 'scope': 'CURRENT_RUNTIME_ONLY'}

    def finalize_session(self, state=None):
        return self.build_session_summary(state=state)

    def get_sessions(self, limit=1):
        return [self.build_session_summary()]

    def clear_session(self):
        with self.lock:
            self._data = self._empty()
            for p in (self.path, self.path.with_suffix(self.path.suffix + '.tmp')):
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
