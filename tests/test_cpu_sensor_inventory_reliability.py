"""Regresión V0.10.0.0w: inventario CPU/GPU no puede romperse al ordenar filas."""
from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def method_has_staticmethod(path: Path, class_name: str, method_name: str) -> bool:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return any(isinstance(dec, ast.Name) and dec.id == 'staticmethod' for dec in item.decorator_list)
    return False


def main():
    cpu_path = ROOT / 'gui' / 'cpu_detail_panel.py'
    gpu_path = ROOT / 'gui' / 'gpu_detail_panel.py'
    cpu_text = cpu_path.read_text(encoding='utf-8')
    gpu_text = gpu_path.read_text(encoding='utf-8')

    results = [
        check('version', VERSION == '0.10.0.0w'),
        check('cpu_sort_is_static', method_has_staticmethod(cpu_path, 'CPUDetailPanel', '_sensor_sort_key')),
        check('gpu_sort_is_static', method_has_staticmethod(gpu_path, 'GPUDetailPanel', '_sensor_sort_key')),
        check('cpu_snapshot_fallback_exists', 'def _snapshot_metric_rows(self, telemetry, snapshot_stamp=None):' in cpu_text),
        check('fallback_requires_valid_real_value', "value is None or quality != 'VALID'" in cpu_text),
        check('fallback_covers_os_usage', "('cpu_usage', 'load', 'Uso total CPU', '%')" in cpu_text),
        check('fallback_covers_frequency', "('cpu_ghz', 'clock', 'Frecuencia CPU', 'GHz')" in cpu_text),
        check('unavailable_temp_not_synthesized', "('cpu_temp', 'temperature', 'Temperatura CPU', '°C')" in cpu_text and "quality != 'VALID'" in cpu_text),
        check('fallback_is_used_after_aggregate', "sensors = self._aggregate_sensor_rows(cpu, snapshot_stamp)" in cpu_text and "sensors = self._snapshot_metric_rows(telemetry, snapshot_stamp)" in cpu_text),
        check('cpu_refresh_errors_logged', 'Fallo al refrescar Detalles avanzados de CPU' in cpu_text),
        check('gpu_refresh_errors_logged', 'Fallo al refrescar Detalles avanzados de GPU' in gpu_text),
        check('cpu_refresh_no_silent_terminal_except', "except Exception:\n            pass\n\n        if self._alive" not in cpu_text),
        check('gpu_refresh_no_silent_terminal_except', "except Exception:\n            pass\n        finally:" not in gpu_text),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
