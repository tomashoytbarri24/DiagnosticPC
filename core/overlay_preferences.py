"""Carga y guarda las preferencias del overlay de CorePulse."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import json
from pathlib import Path
from threading import RLock
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'data'
PREFERENCES_FILE = DATA_DIR / 'overlay_preferences.json'
DEFAULTS = {'layout': 'FULL', 'x': 20, 'y': 20, 'pixel': 1, 'show_fps': True, 'show_frametime': True, 'show_1pct_low': True, 'show_cpu': True, 'show_ram': True, 'show_gpu': True, 'show_storage': True}
_lock = RLock()
_cache = None
_cache_mtime_ns = None

def normalize_preferences(data=None):
    src = data if isinstance(data, dict) else {}
    out = dict(DEFAULTS)
    layout = str(src.get('layout', out['layout']) or '').upper().strip()
    out['layout'] = layout if layout in {'FULL', 'COMPACT'} else 'FULL'
    for key, lo, hi in (('x', 0, 5000), ('y', 0, 5000), ('pixel', 1, 4)):
        try:
            out[key] = max(lo, min(hi, int(src.get(key, out[key]))))
        except Exception:
            out[key] = DEFAULTS[key]
    for key in ('show_fps', 'show_frametime', 'show_1pct_low', 'show_cpu', 'show_ram', 'show_gpu', 'show_storage'):
        value = src.get(key, DEFAULTS[key])
        out[key] = value if isinstance(value, bool) else DEFAULTS[key]
    return out

def _mtime():
    try:
        return PREFERENCES_FILE.stat().st_mtime_ns
    except Exception:
        return None

def load_overlay_preferences(force=False):
    global _cache, _cache_mtime_ns
    with _lock:
        mtime = _mtime()
        if not force and _cache is not None and (mtime == _cache_mtime_ns):
            return dict(_cache)
        try:
            raw = json.loads(PREFERENCES_FILE.read_text(encoding='utf-8')) if PREFERENCES_FILE.exists() else {}
        except Exception:
            raw = {}
        _cache = normalize_preferences(raw)
        _cache_mtime_ns = mtime
        return dict(_cache)

def save_overlay_preferences(data):
    global _cache, _cache_mtime_ns
    value = normalize_preferences(data)
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = PREFERENCES_FILE.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(PREFERENCES_FILE)
        _cache = value
        _cache_mtime_ns = _mtime()
    return dict(value)

def reset_overlay_preferences():
    return save_overlay_preferences(DEFAULTS)
