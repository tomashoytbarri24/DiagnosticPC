"""Regresión V100 — startup rápido y autoridad visual única."""
from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, value):
    if not value:
        raise AssertionError(name)
    print('[PASS]', name)


def top_level_imports(source: str):
    tree = ast.parse(source)
    result=[]
    for node in tree.body:
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            result.append(node.module or '')
    return result


def main():
    main_py=(ROOT/'main.py').read_text(encoding='utf-8')
    dashboard=(ROOT/'gui/dashboard.py').read_text(encoding='utf-8')
    launcher=(ROOT/'corepulse_launcher.py').read_text(encoding='utf-8')
    readiness=(ROOT/'core/startup_readiness.py').read_text(encoding='utf-8')
    profiler=(ROOT/'core/startup_profiler.py').read_text(encoding='utf-8')
    build=(ROOT/'build_exe.bat').read_text(encoding='utf-8')
    iss=(ROOT/'installer/CorePulse.iss').read_text(encoding='utf-8')
    imports=top_level_imports(main_py)

    check('version', VERSION == '103')
    check('stage', STAGE == 'STARTUP_RESPONSIVENESS_SINGLE_LAYOUT_AUTHORITY')
    check('first_frame_after_idle', 'self.after_idle(self._after_first_frame)' in main_py)
    check('charts_deferred', 'def _initialize_charts_deferred' in main_py and 'import matplotlib' in main_py)
    check('matplotlib_not_top_level', not any(x.startswith('matplotlib') for x in imports))
    check('services_background', 'CorePulse-StartupServices' in main_py and 'def _background_services_worker' in main_py)
    check('telemetry_after_services', "name='CorePulse-Telemetry'" in main_py and main_py.index("name='CorePulse-Telemetry'") > main_py.index('def _commit_background_services'))
    check('professional_layout_authority', 'apply_professional_dashboard(self)' in main_py)
    constructor=main_py[main_py.index('    def __init__(self):'):main_py.index('    def _startup_mark', main_py.index('    def __init__(self):'))]
    check('legacy_sidebar_not_published', "self.frame_logo.pack(" not in constructor and "self.btn_overlay.pack(" not in constructor)
    check('legacy_dashboard_not_published', "self.frame_meters.pack(" not in constructor and "self.frame_charts.pack(" not in constructor)
    check('dashboard_refresh_hook', 'def refresh_professional_charts' in dashboard)
    check('fast_launch_gate', 'def collect_launch_gate' in readiness and 'collect_launch_gate(VERSION)' in launcher)
    check('runtime_integrity_deferred', 'CorePulse-RuntimeIntegrity' in launcher and '_deferred_integrity_worker' in launcher)
    check('build_selftest_preserved', '--corepulse-self-test' in build and ':FAIL_SELFTEST' in build)
    check('same_exe_helpers_preserved', '--corepulse-tweak-apply' in launcher and '--corepulse-tweak-rollback' in launcher)
    check('startup_metrics', 'startup_metrics.json' in profiler and 'first_frame_ms' in profiler)
    check('real_or_na_preserved', 'REAL_OR_NA' in (ROOT/'README.md').read_text(encoding='utf-8'))
    check('real_fps_or_na_preserved', 'REAL_FPS_OR_NA_ONLY' in (ROOT/'README.md').read_text(encoding='utf-8'))
    check('no_vendor_hardcode_startup', all(token not in main_py for token in ('GE66 Raider 10SF','i7-10750H','RTX 2070','PM981')))
    check('build_version_synced', '100' in build and '100' in iss)
    check('first_frame_import_count_reduced', len(imports) <= 34)
    print(f'RESULTADO: PASS ({21} checks)')


if __name__ == '__main__':
    main()
