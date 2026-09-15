"""Historial longitudinal de salud para CorePulse.

Persiste únicamente métricas reales observadas. No interpola ni inventa muestras.
V116 añade agregación diaria/semanal, comparación entre períodos y snapshots de
estabilidad sin aumentar la frecuencia de sondeo de hardware.
"""
from __future__ import annotations

import datetime as _dt
import json
import sqlite3
import threading
import time
from pathlib import Path
from core.runtime_paths import data_path
from typing import Any, Dict, List

DB_PATH = data_path('health_history.sqlite3')


def _num(value):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _storage_health(disks):
    vals = []
    for disk in disks or []:
        if isinstance(disk, dict):
            v = _num(disk.get('health'))
            if v is not None:
                vals.append(v)
    return min(vals) if vals else None


def _storage_temp(disks):
    vals = []
    for disk in disks or []:
        if isinstance(disk, dict):
            v = _num(disk.get('temperature_c'))
            if v is not None:
                vals.append(v)
    return max(vals) if vals else None


def _battery_health(telemetry):
    battery = (telemetry or {}).get('_battery') if isinstance(telemetry, dict) else None
    if not isinstance(battery, dict):
        return None
    design = _num(battery.get('designed_capacity_mwh'))
    full = _num(battery.get('full_charge_capacity_mwh'))
    degradation = _num(battery.get('degradation_percent'))
    if design and full and design > 0:
        return max(0.0, min(100.0, full / design * 100.0))
    if degradation is not None:
        return max(0.0, min(100.0, 100.0 - degradation))
    return None


def _battery_degradation(telemetry, health_override=None):
    health = _num(health_override)
    if health is None:
        health = _battery_health(telemetry)
    return max(0.0, min(100.0, 100.0 - health)) if health is not None else None


def _metric_stats(rows, keys):
    result = {}
    for key in keys:
        vals = [_num(r.get(key)) for r in rows]
        vals = [v for v in vals if v is not None]
        result[key] = {
            'count': len(vals),
            'min': min(vals) if vals else None,
            'max': max(vals) if vals else None,
            'avg': sum(vals) / len(vals) if vals else None,
            'first': vals[0] if vals else None,
            'latest': vals[-1] if vals else None,
            'change': (vals[-1] - vals[0]) if len(vals) >= 2 else None,
        }
    return result


class HealthHistoryStore:
    """SQLite thread-safe para muestras espaciadas, benchmarks y comparaciones."""

    METRIC_KEYS = (
        'cpu_temp', 'cpu_usage', 'cpu_clock', 'cpu_power',
        'ram_usage', 'ram_available_gb', 'process_count',
        'gpu_temp', 'gpu_usage', 'storage_health', 'storage_temp_max',
        'battery_health', 'battery_degradation', 'system_score',
    )

    def __init__(self, path: Path | str = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(str(self.path), timeout=6.0)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _ensure_columns(conn, table: str, columns: Dict[str, str]):
        existing = {str(row[1]) for row in conn.execute(f'PRAGMA table_info({table})').fetchall()}
        for name, sql_type in columns.items():
            if name not in existing:
                conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {sql_type}')

    def _init_db(self):
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS health_samples (
                    ts REAL PRIMARY KEY,
                    cpu_temp REAL, cpu_usage REAL, cpu_clock REAL, cpu_power REAL,
                    ram_usage REAL,
                    gpu_temp REAL, gpu_usage REAL,
                    storage_health REAL, battery_health REAL,
                    system_score REAL,
                    payload_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_health_samples_ts ON health_samples(ts);
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    kind TEXT NOT NULL,
                    value REAL,
                    unit TEXT,
                    provider TEXT,
                    duration_s REAL,
                    payload_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_benchmark_runs_ts ON benchmark_runs(ts);
                CREATE TABLE IF NOT EXISTS benchmark_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    profile TEXT NOT NULL,
                    components_json TEXT NOT NULL,
                    suite_json TEXT NOT NULL,
                    compare_json TEXT,
                    hardware_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_benchmark_sessions_ts ON benchmark_sessions(ts);
                CREATE TABLE IF NOT EXISTS stability_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    period_days INTEGER NOT NULL,
                    bsod_bugcheck INTEGER,
                    whea INTEGER,
                    power_incidents INTEGER,
                    app_error INTEGER,
                    app_hang INTEGER,
                    matched_total INTEGER,
                    payload_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_stability_snapshots_ts ON stability_snapshots(ts);
                """
            )
            self._ensure_columns(conn, 'health_samples', {
                'ram_available_gb': 'REAL',
                'process_count': 'REAL',
                'storage_temp_max': 'REAL',
                'battery_degradation': 'REAL',
            })

    def record_snapshot(self, telemetry: Dict[str, Any], disks=None, score=None, ts=None, battery_health_override=None, context=None):
        telemetry = telemetry if isinstance(telemetry, dict) else {}
        cpu = telemetry.get('_cpu') if isinstance(telemetry.get('_cpu'), dict) else {}
        context = context if isinstance(context, dict) else {}
        ts = float(ts or time.time())
        battery_health = _num(battery_health_override)
        if battery_health is None:
            battery_health = _battery_health(telemetry)
        row = (
            ts,
            _num(telemetry.get('cpu_temp')),
            _num(telemetry.get('cpu_usage')),
            _num(telemetry.get('cpu_ghz')),
            _num(cpu.get('package_power_w')),
            _num(telemetry.get('ram_usage')),
            _num(telemetry.get('ram_available_gb')),
            _num(context.get('process_count')),
            _num(telemetry.get('gpu_temp')),
            _num(telemetry.get('gpu_usage')),
            _storage_health(disks),
            _storage_temp(disks),
            battery_health,
            _battery_degradation(telemetry, battery_health),
            _num(score),
            json.dumps({'policy': 'REAL_OR_NA', 'telemetry_version': telemetry.get('_telemetry_version')}, ensure_ascii=False),
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO health_samples
                (ts,cpu_temp,cpu_usage,cpu_clock,cpu_power,ram_usage,ram_available_gb,process_count,
                 gpu_temp,gpu_usage,storage_health,storage_temp_max,battery_health,battery_degradation,system_score,payload_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                row,
            )
        return ts

    def record_stability_snapshot(self, result: Dict[str, Any], period_days: int = 7, ts=None):
        """Guarda un resumen ya calculado por Análisis de Windows.

        No dispara consultas de eventos por su cuenta. Así el historial reutiliza
        trabajo que el usuario ya pidió y evita procesos repetidos al entrar.
        """
        if not isinstance(result, dict) or result.get('error'):
            return None
        counts = result.get('counts') if isinstance(result.get('counts'), dict) else {}
        if not counts:
            counts = result.get('Counts') if isinstance(result.get('Counts'), dict) else {}
        power_incidents = result.get('power_incident_count')
        if power_incidents is None:
            power_incidents = result.get('PowerIncidentCount')
        matched = result.get('matched_total')
        if matched is None:
            matched = result.get('MatchedTotal')
        stamp = float(ts or time.time())
        period_days = max(1, int(period_days or 7))
        # Como el análisis suele repetirse manualmente, sustituimos una captura muy
        # próxima del mismo período para no llenar la BD con duplicados idénticos.
        with self._lock, self._connect() as conn:
            recent = conn.execute(
                'SELECT id,ts FROM stability_snapshots WHERE period_days=? ORDER BY ts DESC LIMIT 1',
                (period_days,),
            ).fetchone()
            values = (
                int(counts.get('bsod_bugcheck') or 0),
                int(counts.get('whea') or 0),
                int(power_incidents or 0),
                int(counts.get('app_error') or 0),
                int(counts.get('app_hang') or 0),
                int(matched or 0),
                json.dumps(result, ensure_ascii=False, default=str),
            )
            if recent is not None and stamp - float(recent['ts']) < 1800:
                conn.execute(
                    """UPDATE stability_snapshots SET ts=?,bsod_bugcheck=?,whea=?,power_incidents=?,app_error=?,app_hang=?,matched_total=?,payload_json=? WHERE id=?""",
                    (stamp, *values, int(recent['id'])),
                )
                return int(recent['id'])
            cur = conn.execute(
                """INSERT INTO stability_snapshots(ts,period_days,bsod_bugcheck,whea,power_incidents,app_error,app_hang,matched_total,payload_json)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (stamp, period_days, *values),
            )
            return cur.lastrowid

    def latest_stability_snapshots(self, limit: int = 12, period_days: int | None = None):
        with self._lock, self._connect() as conn:
            if period_days is None:
                rows = conn.execute(
                    'SELECT * FROM stability_snapshots ORDER BY ts DESC,id DESC LIMIT ?',
                    (max(1, int(limit)),),
                ).fetchall()
            else:
                rows = conn.execute(
                    'SELECT * FROM stability_snapshots WHERE period_days=? ORDER BY ts DESC,id DESC LIMIT ?',
                    (max(1, int(period_days)), max(1, int(limit))),
                ).fetchall()
        return [dict(row) for row in rows]

    def record_benchmark(self, result: Dict[str, Any]):
        if not isinstance(result, dict):
            return None
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO benchmark_runs(ts,kind,value,unit,provider,duration_s,payload_json)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    float(result.get('timestamp') or time.time()),
                    str(result.get('kind') or 'unknown'),
                    _num(result.get('value')),
                    str(result.get('unit') or ''),
                    str(result.get('provider') or ''),
                    _num(result.get('duration_s')),
                    json.dumps(result, ensure_ascii=False),
                ),
            )
            return cur.lastrowid

    def query_range(self, start_ts: float, end_ts: float, limit: int = 10000) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM health_samples WHERE ts>=? AND ts<? ORDER BY ts ASC LIMIT ?',
                (float(start_ts), float(end_ts), max(1, int(limit))),
            ).fetchall()
        return [dict(r) for r in rows]

    def query(self, days: int = 7, limit: int = 5000) -> List[Dict[str, Any]]:
        since = time.time() - max(1, int(days)) * 86400
        return self.query_range(since, time.time() + 1.0, limit=limit)

    def latest_benchmarks(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute('SELECT * FROM benchmark_runs ORDER BY ts DESC LIMIT ?', (max(1, int(limit)),)).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            try:
                d['payload'] = json.loads(d.pop('payload_json') or '{}')
            except Exception:
                d['payload'] = {}
            out.append(d)
        return out

    def record_benchmark_session(
        self,
        suite: Dict[str, Any],
        *,
        profile: str | None = None,
        components=None,
        comparison: Dict[str, Any] | None = None,
        hardware: Dict[str, Any] | None = None,
    ):
        if not isinstance(suite, dict):
            return None
        normalized_components = []
        source_components = components if components is not None else suite.get('selected_components')
        for item in source_components or []:
            key = str(item or '').strip().lower()
            if key and key not in normalized_components:
                normalized_components.append(key)
        profile_key = str(profile or suite.get('profile') or 'standard').strip().upper()
        ts = _num(suite.get('finished_at')) or _num(suite.get('started_at')) or time.time()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO benchmark_sessions(ts,profile,components_json,suite_json,compare_json,hardware_json)
                VALUES (?,?,?,?,?,?)""",
                (
                    float(ts),
                    profile_key,
                    json.dumps(normalized_components, ensure_ascii=False),
                    json.dumps(suite, ensure_ascii=False, default=str),
                    json.dumps(comparison or {}, ensure_ascii=False, default=str),
                    json.dumps(hardware or {}, ensure_ascii=False, default=str),
                ),
            )
            return cur.lastrowid

    def latest_benchmark_sessions(self, limit: int = 12) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM benchmark_sessions ORDER BY ts DESC, id DESC LIMIT ?',
                (max(1, int(limit)),),
            ).fetchall()
        out = []
        for row in rows:
            data = dict(row)
            for source_key, target_key, fallback in (
                ('components_json', 'components', []),
                ('suite_json', 'suite', {}),
                ('compare_json', 'comparison', {}),
                ('hardware_json', 'hardware', {}),
            ):
                raw = data.pop(source_key, None)
                try:
                    data[target_key] = json.loads(raw or ('[]' if isinstance(fallback, list) else '{}'))
                except Exception:
                    data[target_key] = fallback
            out.append(data)
        return out

    def summary_range(self, start_ts: float, end_ts: float, limit: int = 10000) -> Dict[str, Any]:
        rows = self.query_range(start_ts, end_ts, limit=limit)
        return {
            'samples': len(rows),
            'from_ts': rows[0]['ts'] if rows else None,
            'to_ts': rows[-1]['ts'] if rows else None,
            'metrics': _metric_stats(rows, self.METRIC_KEYS),
        }

    def summary(self, days: int = 7) -> Dict[str, Any]:
        days = max(1, int(days))
        result = self.summary_range(time.time() - days * 86400, time.time() + 1.0)
        result['days'] = days
        return result

    def daily_summary(self, days: int = 30) -> List[Dict[str, Any]]:
        """Agrupa muestras reales por día local para una cronología legible."""
        days = max(1, min(365, int(days)))
        rows = self.query(days=days, limit=50000)
        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            key = _dt.datetime.fromtimestamp(float(row['ts'])).date().isoformat()
            buckets.setdefault(key, []).append(row)
        out = []
        for day in sorted(buckets):
            items = buckets[day]
            out.append({
                'date': day,
                'samples': len(items),
                'from_ts': items[0]['ts'],
                'to_ts': items[-1]['ts'],
                'metrics': _metric_stats(items, self.METRIC_KEYS),
            })
        return out

    def compare_periods(self, days: int = 7) -> Dict[str, Any]:
        """Compara el período actual con el bloque inmediatamente anterior."""
        days = max(1, min(90, int(days)))
        now = time.time()
        current = self.summary_range(now - days * 86400, now + 1.0)
        previous = self.summary_range(now - 2 * days * 86400, now - days * 86400)
        metrics = {}
        for key in self.METRIC_KEYS:
            c = (current.get('metrics') or {}).get(key) or {}
            p = (previous.get('metrics') or {}).get(key) or {}
            metric = {'current': c, 'previous': p}
            for stat in ('avg', 'max', 'min', 'latest'):
                cv, pv = _num(c.get(stat)), _num(p.get(stat))
                metric[f'{stat}_delta'] = (cv - pv) if cv is not None and pv is not None else None
            metrics[key] = metric
        return {
            'days': days,
            'current': current,
            'previous': previous,
            'metrics': metrics,
            'comparable': bool(current.get('samples') and previous.get('samples')),
            'policy': 'OBSERVED_PERIODS_ONLY',
        }

    def trend_insights(self, days: int = 7) -> List[Dict[str, Any]]:
        """Genera frases a partir de deltas observados, sin afirmar causalidad."""
        comp = self.compare_periods(days)
        if not comp.get('comparable'):
            return []
        insights = []
        specs = (
            ('cpu_temp', 'Temperatura máxima CPU', 'max_delta', ' °C', 2.0),
            ('gpu_temp', 'Temperatura máxima GPU', 'max_delta', ' °C', 2.0),
            ('ram_usage', 'Uso medio de RAM', 'avg_delta', ' pp', 3.0),
            ('system_score', 'Índice medio del sistema', 'avg_delta', ' pts', 2.0),
        )
        for key, label, delta_key, unit, threshold in specs:
            delta = _num((comp.get('metrics') or {}).get(key, {}).get(delta_key))
            if delta is None or abs(delta) < threshold:
                continue
            insights.append({
                'metric': key,
                'label': label,
                'delta': delta,
                'unit': unit,
                'direction': 'up' if delta > 0 else 'down',
                'text': f'{label}: {delta:+.1f}{unit} frente a los {days} días anteriores.',
            })
        # Salud de batería/almacenamiento se expresa como cambio dentro del período,
        # no como diagnóstico de causa ni pronóstico de degradación.
        current_metrics = (comp.get('current') or {}).get('metrics') or {}
        for key, label in (('battery_health', 'Salud de batería'), ('storage_health', 'Salud de almacenamiento')):
            change = _num((current_metrics.get(key) or {}).get('change'))
            if change is not None and abs(change) >= 0.5:
                insights.append({
                    'metric': key,
                    'label': label,
                    'delta': change,
                    'unit': ' pp',
                    'direction': 'up' if change > 0 else 'down',
                    'text': f'{label}: {change:+.1f} pp entre la primera y la última lectura válida del período.',
                })
        return insights
