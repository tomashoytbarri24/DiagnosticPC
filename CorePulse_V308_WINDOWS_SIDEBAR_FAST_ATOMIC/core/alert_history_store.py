"""Mantiene el historial de alertas activo durante la sesión de CorePulse."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import copy, datetime as dt, threading
from core.alert_history_persistence import PersistentAlertHistory
MAX_SESSION_ALERTS = 10

def _fmt_ts(value):
    if not isinstance(value, (int, float)):
        return '--'
    try:
        return dt.datetime.fromtimestamp(value).strftime('%H:%M:%S')
    except Exception:
        return '--'

class AlertHistoryStore:
    """Clase responsable de `AlertHistoryStore` dentro de CorePulse. Conserva los contratos de integridad del módulo."""

    def __init__(self, agent, persistence=None):
        self.agent = agent
        self.lock = threading.RLock()
        self._rows = []
        self.persistence = persistence or PersistentAlertHistory(max_events=MAX_SESSION_ALERTS)

    @staticmethod
    def _row(event, status):
        return {'key': event.get('key'), 'status': status, 'component': event.get('component', 'SYSTEM'), 'level': event.get('level', 'INFO'), 'title': event.get('title', ''), 'detail': event.get('detail', ''), 'evidence': list(event.get('evidence') or []), 'context': event.get('context', 'UNKNOWN'), 'first_seen': event.get('first_seen'), 'first_seen_text': _fmt_ts(event.get('first_seen')), 'last_seen': event.get('last_seen'), 'last_seen_text': _fmt_ts(event.get('last_seen')), 'resolved_at': event.get('resolved_at'), 'resolved_at_text': _fmt_ts(event.get('resolved_at')), 'occurrences': int(event.get('occurrences') or 0), 'active': bool(event.get('active'))}

    def refresh(self):
        state = self.agent.get_state() if self.agent is not None else {}
        alerts = (state or {}).get('alerts') or {}
        current = []
        for event in alerts.get('active') or []:
            if isinstance(event, dict):
                current.append(self._row(event, 'ACTIVE'))
        for event in alerts.get('history') or []:
            if isinstance(event, dict):
                current.append(self._row(event, 'RESOLVED'))
        self.persistence.sync_rows(current)
        rows = self.persistence.get_events(limit=MAX_SESSION_ALERTS)
        with self.lock:
            self._rows = rows
        return copy.deepcopy(rows)

    def rows(self):
        with self.lock:
            return copy.deepcopy(self._rows)

    def summary(self):
        with self.lock:
            rows = list(self._rows)
        active = [r for r in rows if r.get('status') == 'ACTIVE']
        resolved = [r for r in rows if r.get('status') == 'RESOLVED']
        return {'active': len(active), 'critical': sum((1 for r in active if r.get('level') == 'CRITICAL')), 'warning': sum((1 for r in active if r.get('level') == 'WARNING')), 'info': sum((1 for r in active if r.get('level') == 'INFO')), 'resolved': len(resolved), 'history_count': len(rows), 'session_total': len(rows), 'limit': MAX_SESSION_ALERTS}

    def finalize_session(self):
        self.refresh()
        return self.persistence.finalize_session(state=self.agent.get_state())

    def session_summaries(self, limit=1):
        return self.persistence.get_sessions(limit=limit)

    def close_session(self):
        self.persistence.clear_session()
        with self.lock:
            self._rows = []
