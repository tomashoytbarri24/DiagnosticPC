"""Persistencia transaccional del estado de energía previo a CorePulse."""
from __future__ import annotations
import json
import logging
import os
import time
from pathlib import Path
from core.runtime_paths import data_path
from typing import Any, Dict, Optional

STATE_PATH = data_path('performance_power_backup.json')
logger = logging.getLogger('CorePulse.ProfileBackup')


def load_backup(path: Path = STATE_PATH) -> Optional[Dict[str, Any]]:
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else None
    except Exception:
        logger.exception('[PROFILE] No se pudo leer el backup de energía: %s', path)
        return None


def save_backup(payload: Dict[str, Any], path: Path = STATE_PATH) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(payload or {})
    data.setdefault('schema_version', 1)
    data.setdefault('created_at', time.time())
    data['pending_restore'] = True
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)
    return data


def mark_restored(path: Path = STATE_PATH) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        # Si Windows mantiene el archivo ocupado, al menos se evita marcarlo como pendiente.
        try:
            data = load_backup(path) or {}
            data['pending_restore'] = False
            data['restored_at'] = time.time()
            tmp = path.with_suffix(path.suffix + '.tmp')
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(tmp, path)
        except Exception:
            logger.exception('[PROFILE] No se pudo marcar el backup de energía como restaurado: %s', path)


def has_pending_backup(path: Path = STATE_PATH) -> bool:
    data = load_backup(path)
    return bool(data and data.get('pending_restore', True))
