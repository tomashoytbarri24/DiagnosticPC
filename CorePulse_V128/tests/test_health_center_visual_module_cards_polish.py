"""Compatibilidad visual base de tarjetas de salud V100."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    results = [
        check('version', VERSION == '103'),
        check('helper_exists', 'def _health_module_visual_profile(self, title):' in panel),
        check('estado_actual_label', "text='Estado actual'" in panel),
        check('icon_plain_render', 'icon_label = ctk.CTkLabel(' in panel),
        check('button_render', "variant='secondary', height=29" in panel),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
