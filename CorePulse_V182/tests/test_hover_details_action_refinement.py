"""V100 — `Ver detalles` sólo aparece al hacer hover en cards del Resumen."""
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
    dash = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    storage = (ROOT / 'gui' / 'hardware_storage_view.py').read_text(encoding='utf-8')
    checks = [
        check('version', VERSION.isdecimal()),
        check('stage_preserved', bool(STAGE)),
        check('dashboard_hover_accepts_action', 'action_button=None, action_place=None' in dash),
        check('dashboard_action_hidden_at_rest', 'bind_node(root)\n    hide_action()' in dash),
        check('dashboard_action_revealed_on_hover', '_safe_config(root, fg_color=hover)\n        show_action()' in dash),
        check('dashboard_leave_pointer_guard', 'if not inside_root()' in dash and 'hide_action()' in dash),
        check('cpu_hover_action', 'action_button=app._cpu_details_button' in dash),
        check('ram_hover_action', 'action_button=app._ram_details_button' in dash),
        check('gpu_hover_action', 'action_button=app._gpu_details_button' in dash),
        check('no_permanent_metric_button_place', '_cpu_details_button.place(' not in dash and '_ram_details_button.place(' not in dash and '_gpu_details_button.place(' not in dash),
        check('storage_hover_helper', 'def _bind_storage_hover_action(card, details, badge):' in storage),
        check('storage_hidden_at_rest', 'details.pack_forget()' in storage),
        check('storage_reinserted_right_of_badge', "details.pack(side='right', padx=(8, 0), before=badge)" in storage),
        check('storage_pointer_guard', 'if inside_card()' in storage),
        check('storage_hook_applied', '_bind_storage_hover_action(card, details, badge)' in storage),
        check('button_language_preserved', "text='Ver detalles'" in dash and "text='Ver detalles'" in storage),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
