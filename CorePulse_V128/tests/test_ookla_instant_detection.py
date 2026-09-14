"""V100 — detección inmediata de Ookla tras instalación con winget."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
import core.internet_speed_test as speed


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    installer = (ROOT / 'Instalar_Speedtest_Ookla.bat').read_text(encoding='utf-8')
    engine = (ROOT / 'core' / 'internet_speed_test.py').read_text(encoding='utf-8')

    original_local = os.environ.get('LOCALAPPDATA')
    original_which = speed.shutil.which
    try:
        with tempfile.TemporaryDirectory() as td:
            local = Path(td)
            link = local / 'Microsoft' / 'WinGet' / 'Links' / 'speedtest.exe'
            link.parent.mkdir(parents=True, exist_ok=True)
            link.write_bytes(b'fake')
            os.environ['LOCALAPPDATA'] = str(local)
            speed.shutil.which = lambda _: None
            candidates = [str(p) for p in speed._candidate_ookla_paths()]
            link_seen = str(link) in candidates
    finally:
        speed.shutil.which = original_which
        if original_local is None:
            os.environ.pop('LOCALAPPDATA', None)
        else:
            os.environ['LOCALAPPDATA'] = original_local

    checks = [
        check('version', VERSION == '103'),
        check('engine_checks_winget_links', "'WinGet' / 'Links' / 'speedtest.exe'" in engine),
        check('candidate_includes_winget_link_without_path', link_seen),
        check('installer_checks_winget_links', r'%LOCALAPPDATA%\Microsoft\WinGet\Links\speedtest.exe' in installer),
        check('installer_checks_package_directory', 'Ookla.Speedtest.CLI_*' in installer),
        check('installer_uses_resolved_exe', '"%SPEEDTEST_EXE%" --version' in installer and '"%SPEEDTEST_EXE%"' in installer),
        check('no_restart_requirement', 'reinicia CorePulse' not in installer and 'reinicia Windows' not in installer),
        check('no_auto_acceptance', '--accept-license' not in installer and '--accept-gdpr' not in installer),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
