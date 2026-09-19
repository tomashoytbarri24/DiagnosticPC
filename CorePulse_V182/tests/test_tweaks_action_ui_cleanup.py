"""V100 — controles de Tweaks agrupados sin sobrecarga visual."""
from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    panel = (ROOT/'gui'/'windows_tweaks_panel.py').read_text(encoding='utf-8')
    checks = [
        check('version', VERSION.isdecimal()),
        check('single_preset_dropdown', 'self.preset_menu = ctk.CTkOptionMenu' in panel and 'def _on_preset_selected' in panel),
        check('six_preset_buttons_removed', "for key in ('recommended', 'minimal', 'privacy', 'gaming', 'performance', 'advanced')" not in panel),
        check('quick_selection_group', "text='SELECCIÓN'" in panel and "text='Seleccionar todos los tweaks'" in panel and "text='Con rollback'" in panel),
        check('refresh_is_secondary', "text='Actualizar estado'" in panel),
        check('undo_collapsed_to_menu', "text='Deshacer cambios  ▾'" in panel and 'def _show_undo_menu' in panel),
        check('undo_selected_retained', "label='Deshacer seleccionados'" in panel),
        check('undo_all_retained', "label='Deshacer TODO lo aplicado'" in panel),
        check('explorer_restart_contextual', 'def _set_restart_available' in panel and 'self.btn_restart.pack_forget()' in panel),
        check('primary_apply_retained', "text='Aplicar seleccionados'" in panel),
        check('rollback_engine_unchanged_route', "command=lambda: self._run_batch('apply')" in panel and "command=lambda: self._run_batch('undo')" in panel and 'command=self._run_undo_all' in panel),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
