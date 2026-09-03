"""Historial longitudinal de salud para CorePulse.

Persiste únicamente métricas reales observadas. No interpola ni inventa muestras.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'data' / 'health_history.sqlite3'


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


class HealthHistoryStore:
    """SQLite thread-safe para muestras espaciadas, benchmarks y comparaciones."""

    def __init__(self, path: Path | str = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(str(self.path), timeout=6.0)
        conn.row_factory = sqlite3.Row
        return conn

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
                """
            )

    def record_snapshot(self, telemetry: Dict[str, Any], disks=None, score=None, ts=None, battery_health_override=None):
        telemetry = telemetry if isinstance(telemetry, dict) else {}
        cpu = telemetry.get('_cpu') if isinstance(telemetry.get('_cpu'), dict) else {}
        ts = float(ts or time.time())
        row = (
            ts,
            _num(telemetry.get('cpu_temp')),
            _num(telemetry.get('cpu_usage')),
            _num(telemetry.get('cpu_ghz')),
            _num(cpu.get('package_power_w')),
            _num(telemetry.get('ram_usage')),
            _num(telemetry.get('gpu_temp')),
            _num(telemetry.get('gpu_usage')),
            _storage_health(disks),
            _num(battery_health_override) if _num(battery_health_override) is not None else _battery_health(telemetry),
            _num(score),
            json.dumps({'policy': 'REAL_OR_NA', 'telemetry_version': telemetry.get('_telemetry_version')}, ensure_ascii=False),
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO health_samples
                (ts,cpu_temp,cpu_usage,cpu_clock,cpu_power,ram_usage,gpu_temp,gpu_usage,storage_health,battery_health,system_score,payload_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                row,
            )
        return ts

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

    def query(self, days: int = 7, limit: int = 5000) -> List[Dict[str, Any]]:
        since = time.time() - max(1, int(days)) * 86400
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM health_samples WHERE ts>=? ORDER BY ts ASC LIMIT ?",
                (since, max(1, int(limit))),
            ).fetchall()
        return [dict(r) for r in rows]

    def latest_benchmarks(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM benchmark_runs ORDER BY ts DESC LIMIT ?", (max(1, int(limit)),)).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            try:
                d['payload'] = json.loads(d.pop('payload_json') or '{}')
            except Exception:
                d['payload'] = {}
            out.append(d)
        return out

    def summary(self, days: int = 7) -> Dict[str, Any]:
        rows = self.query(days=days)
        keys = ('cpu_temp','cpu_usage','cpu_clock','cpu_power','ram_usage','gpu_temp','gpu_usage','storage_health','battery_health','system_score')
        stats = {'days': int(days), 'samples': len(rows), 'from_ts': rows[0]['ts'] if rows else None, 'to_ts': rows[-1]['ts'] if rows else None, 'metrics': {}}
        for key in keys:
            vals = [_num(r.get(key)) for r in rows]
            vals = [v for v in vals if v is not None]
            stats['metrics'][key] = {
                'count': len(vals),
                'min': min(vals) if vals else None,
                'max': max(vals) if vals else None,
                'avg': sum(vals) / len(vals) if vals else None,
                'latest': vals[-1] if vals else None,
            }
        return stats
