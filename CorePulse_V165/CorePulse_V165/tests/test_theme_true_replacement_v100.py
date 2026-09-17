"""Regresión V100 — los temas reemplazan la paleta, no aplican un filtro sobre CorePulse."""
from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
import core.theme_manager as tm


def check(name, cond):
    ok = bool(cond)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    if not ok:
        raise AssertionError(name)


def main():
    check('numeric_versioning', VERSION == '103')
    profiles = tm.get_theme_profiles()
    check('ten_themes_preserved', len(profiles) == 10)

    old_file = tm._THEME_FILE
    try:
        with tempfile.TemporaryDirectory() as td:
            tm._THEME_FILE = Path(td) / 'ui_theme.json'
            for key, profile in profiles.items():
                tm.set_theme(key)
                if key == tm.DEFAULT_THEME:
                    continue
                checks = {
                    '#06111f': 'bg',
                    '#0d1828': 'surface',
                    '#0a1524': 'surface_2',
                    '#071522': 'sidebar',
                    '#1b3048': 'border',
                    '#f4f7fb': 'text',
                    '#b8c4d4': 'text_2',
                    '#7f91a8': 'muted',
                    '#14b8ff': 'accent',
                    '#164f7d': 'accent_2',
                }
                for source, role in checks.items():
                    actual = tm.color(source)
                    expected = profile[role]
                    check(f'{key}_{role}_exact', actual.lower() == expected.lower())
                    check(f'{key}_{role}_idempotent', tm.color(actual).lower() == expected.lower())
    finally:
        tm._THEME_FILE = old_file

    source = (ROOT / 'core' / 'theme_manager.py').read_text(encoding='utf-8')
    check('no_mix_in_active_color_path', 'return _theme_role_color(value, _THEME_PROFILES[theme])' in source)
    check('palette_is_role_based', '_ROLE_ALIASES' in source and '_ROLE_BY_COLOR' in source)
    print('\nRESULTADO: PASS')


if __name__ == '__main__':
    main()
