"""Regresión visual mínima para consistencia del botón de almacenamiento."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, condition):
    return name, bool(condition)


def run():
    root = ROOT
    main_text = (root / 'main.py').read_text(encoding='utf-8')
    storage_text = (root / 'gui' / 'hardware_storage_view.py').read_text(encoding='utf-8')
    expected_tokens = [
        "width=92",
        "height=24",
        "fg_color=theme_color('#0d2942')",
        "hover_color=theme_color('#164f7d')",
        "border_width=1",
        "border_color=theme_color('#1d5278')",
        "text_color=theme_color('#75d2f7')",
        "font=('Segoe UI', 8, 'bold')",
    ]
    checks = [check('version', VERSION == '0.10.0.0w')]
    checks.append(check('main_disk_button_present', "text='Ver detalles'" in main_text))
    checks.append(check('storage_style_hook_present', "_cfg(details, text='Ver detalles'" in storage_text))
    for token in expected_tokens:
        checks.append(check(f'main_has_{token}', token in main_text))
        checks.append(check(f'storage_has_{token}', token in storage_text))
    return checks


if __name__ == '__main__':
    results = run()
    failed = [name for name, ok in results if not ok]
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'} - {name}")
    raise SystemExit(1 if failed else 0)
