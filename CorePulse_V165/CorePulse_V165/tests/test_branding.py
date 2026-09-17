"""Valida recursos de marca y referencias activas de CorePulse."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
assets = [
    ROOT / 'assets' / 'CorePulseIcon.png',
    ROOT / 'assets' / 'CorePulseSymbol.png',
    ROOT / 'assets' / 'CorePulseSymbolWhite.png',
    ROOT / 'assets' / 'CorePulseWindowIcon.png',
    ROOT / 'assets' / 'app_icon.ico',
]

checks = {
    'brand_assets_exist': all(path.exists() for path in assets),
    'png_assets_are_512': all(Image.open(path).size == (512, 512) for path in assets[:4]),
    'white_symbol_has_transparency': Image.open(ROOT / 'assets' / 'CorePulseSymbolWhite.png').convert('RGBA').getextrema()[3][0] == 0,
}
ico = Image.open(ROOT / 'assets' / 'app_icon.ico')
checks['windows_icon_has_multi_sizes'] = {(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)}.issubset(set(ico.ico.sizes()))
refs = {
    'main.py': ['app_icon.ico', 'CorePulseWindowIcon.png', 'brand_symbol_path', 'CorePulseIcon.png'],
    'gui/dashboard.py': ['brand_symbol_path', 'sidebar_assets_path'],
    'core/tray_service.py': ['CorePulseSymbol.png'],
    'core/report_builder.py': ['CorePulseIcon.png'],
}
checks['runtime_references_brand_assets'] = all(all(name in (ROOT / rel).read_text(encoding='utf-8', errors='ignore') for name in names) for rel, names in refs.items())
checks['runtime_uses_corepulse_name'] = 'DiagnosticPC' not in '\n'.join(
    path.read_text(encoding='utf-8', errors='ignore')
    for path in [ROOT / 'main.py', *sorted((ROOT / 'core').glob('*.py')), *sorted((ROOT / 'gui').glob('*.py'))]
)
for name, ok in checks.items():
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {bool(ok)}")
print('\nRESULTADO:', 'PASS' if all(checks.values()) else 'FAIL')
raise SystemExit(0 if all(checks.values()) else 1)
