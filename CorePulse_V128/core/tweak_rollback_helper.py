"""Helper elevado de rollback para CorePulse.

El proceso NO carga ni modifica el almacén persistente. Recibe snapshots exactos
serializados por el proceso dueño, los restaura bajo UAC y devuelve resultados.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import windows_tweaks as wt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    args = parser.parse_args()
    request_path = Path(args.request)
    payload = json.loads(request_path.read_text(encoding='utf-8'))
    records = payload.get('records') or []
    result_path = Path(payload['result_path'])
    results = wt.restore_snapshot_records(records, attempts=3)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps({'results': results}, ensure_ascii=False), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
