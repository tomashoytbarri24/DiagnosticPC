"""V128 — paridad exacta entre la previsualización de Temas y la UI real."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
import core.theme_manager as tm


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print('[PASS]', name)


def sha256(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def main():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    consistency = (ROOT / 'gui' / 'ui_consistency.py').read_text(encoding='utf-8')
    startup = (ROOT / 'gui' / 'startup_gate.py').read_text(encoding='utf-8')
    panel = (ROOT / 'gui' / 'theme_panel.py').read_text(encoding='utf-8')
    mainpy = (ROOT / 'main.py').read_text(encoding='utf-8')
    storage = (ROOT / 'gui' / 'hardware_storage_view.py').read_text(encoding='utf-8')

    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))

    # La autoridad de paleta debe devolver el hexadecimal literal definido por el tema.
    for key, profile in tm.get_theme_profiles().items():
        for role in ('bg', 'surface', 'surface_2', 'sidebar', 'border', 'text', 'text_2', 'muted', 'accent', 'accent_2'):
            check(f'exact_role:{key}:{role}', tm.role_color(role, key) == profile[role])
            check(f'exact_preview:{key}:{role}', tm.preview_color(key, role) == profile[role])

    check('dashboard_direct_roles', all(token in dashboard for token in (
        "'app': role_color('bg')", "'sidebar': role_color('sidebar')",
        "'surface': role_color('surface')", "'surface_2': role_color('surface_2')",
        "'border': role_color('border')", "'primary': role_color('accent')",
    )))
    check('sidebar_active_matches_preview', all(token in dashboard for token in (
        "SIDEBAR_ACTIVE_BG = role_color('accent_2')",
        "SIDEBAR_ACTIVE_HOVER = role_color('accent')",
        "text_color=COLORS['text'] if active else SIDEBAR_INACTIVE_TEXT",
    )))
    check('layout_sidebar_same_contract', all(token in layout for token in (
        "SIDEBAR_ACTIVE_BG = role_color('accent_2')",
        "SIDEBAR_ACTIVE_HOVER = role_color('accent')",
        "text_color=TEXT if active else SIDEBAR_INACTIVE_TEXT",
    )))
    check('consistency_sidebar_same_contract', all(token in consistency for token in (
        "ACTIVE_BG = role_color('accent_2')", "ACTIVE_HOVER = role_color('accent')",
        "ACTIVE_TEXT = role_color('text')",
    )))

    # Los paneles visuales grandes usan surface_2, igual que el panel Activity del mock.
    check('dashboard_chart_surface_2', "fg_color=COLORS['surface_2']" in dashboard and "app.fig.set_facecolor(COLORS['surface_2'])" in dashboard)
    check('layout_chart_surface_2', "_cfg(app.frame_charts, fg_color=SURFACE_2" in layout and "app.fig.set_facecolor(SURFACE_2)" in layout)
    check('storage_surface_2', "SURFACE = role_color('surface_2')" in storage)
    check('startup_surface_2', "CARD = role_color('surface_2')" in startup and "PROGRESS_TRACK = role_color('border')" in startup)
    check('main_first_frame_roles', all(token in mainpy for token in (
        "BG_MAIN = role_color('bg')", "BG_CARD = role_color('surface')",
        "BG_SIDEBAR = role_color('sidebar')", "BORDER_COLOR = role_color('border')",
        "fg_color=role_color('surface_2')",
    )))

    # El selector no puede dejar el canvas/scroll en el gris por defecto de CTk.
    check('theme_picker_explicit_surface', "self.scroll = ctk.CTkScrollableFrame(" in panel and "scrollbar_fg_color=p['surface']" in panel)
    check('theme_preview_explicit_surfaces', all(token in panel for token in (
        "mock = ctk.CTkFrame(right, fg_color=p['bg']",
        "side = ctk.CTkFrame(mock, width=126, corner_radius=10, fg_color=p['sidebar'])",
        "card = ctk.CTkFrame(content, fg_color=p['surface']",
        "chart = ctk.CTkFrame(content, fg_color=p['surface_2']",
    )))
    check('theme_controls_use_palette_text', "text_color='#ffffff' if p['appearance']" not in panel and "text_color=p['text']" in panel)

    expected = {
        'core/runtime_venv_path.py': '263d725dc8a50ef57d2e0dd8d8827968f58d2b67dcee6b0a276ca6dd8d562e92',
        'bootstrap_corepulse.py': '925d4ef090b28c27ceffbbbba9362a8137f665212ac445e96a096c0ce5e17a0b',
        'core/source_runtime_bootstrap.py': 'bde37780c35ebc280b0b22ac6a71926051ae9fde48b65935b6af64b819f7ccfd',
        'requirements-runtime-lock.txt': '36ee044c5dab3c5c8cfecbe0456923c9f406d83a93ef04d93f9fd27f1566c706',
        'core/nvme_smart_windows.py': 'fe9481d270d5b47299b97fc97d37ee56f65bd904333f634255e4a91e63958283',
    }
    for rel, digest in expected.items():
        check(f'protected_unchanged:{rel}', sha256(rel) == digest)

    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
