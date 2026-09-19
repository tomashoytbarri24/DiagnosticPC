"""Regresión funcional de Health Center Module Identity Enhancement V100."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    results = [
        check('version', VERSION.isdecimal()),
        check('stage', bool(STAGE)),
        check('battery_category', "'category': 'Autonomía y desgaste'" in panel),
        check('windows_icon', "'icon': '🪟'" in panel),
        check('repair_category', "'category': 'DISM y SFC'" in panel),
        check('history_tags', "'tags': ('Antes/Después', 'Benchmark', 'Cambios HW')" in panel),
        check('recovery_tags', "'tags': ('Restauración', 'Rollback', 'Seguridad')" in panel),
        check('performance_tags', "'tags': ('Throttling', 'Benchmark', 'Perfiles')" in panel),
        check('plain_icon_render', 'icon_label = ctk.CTkLabel(' in panel),
        check('tags_row_render', "tags_row = ctk.CTkFrame(card, fg_color='transparent')" in panel),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
