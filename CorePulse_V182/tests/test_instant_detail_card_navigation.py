"""V100 — las tarjetas de hardware responden antes de construir vistas pesadas."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    nav = (ROOT / 'gui' / 'internal_navigation.py').read_text(encoding='utf-8')
    main_src = (ROOT / 'main.py').read_text(encoding='utf-8')
    storage = (ROOT / 'gui' / 'storage_detail_panel.py').read_text(encoding='utf-8')
    cpu = (ROOT / 'gui' / 'cpu_detail_panel.py').read_text(encoding='utf-8')
    ram = (ROOT / 'gui' / 'ram_detail_panel.py').read_text(encoding='utf-8')
    gpu = (ROOT / 'gui' / 'gpu_detail_panel.py').read_text(encoding='utf-8')
    cache_decl = nav.split('CACHEABLE_PAGES = {', 1)[1].split('}', 1)[0]
    helper = main_src.split('def _open_deferred_hardware_detail', 1)[1].split('def open_cpu_details', 1)[0]
    storage_open = storage.split('def show_storage_details', 1)[1].split('__all__', 1)[0]

    checks = [
        check('version', VERSION.isdecimal()),
        check('stage_preserved', bool(STAGE)),
        check('hardware_details_cached', all(repr(k) in cache_decl for k in ('cpu_details', 'ram_details', 'gpu_details', 'storage_details'))),
        check('attach_panel_without_second_commit', 'def attach_internal_page_panel' in nav and 'polish_widget_tree(host)' not in nav.split('def attach_internal_page_panel',1)[1].split('def abort_internal_page',1)[0]),
        check('shell_committed_before_heavy_factory', helper.find('commit_internal_page(self, page_key, host, panel=None)') < helper.find('panel = factory(host)')),
        check('detail_build_deferred_one_frame', 'self._defer_ui_call(build_panel, 16)' in helper),
        check('no_forced_update_idletasks_in_detail_path', 'self.update_idletasks()' not in helper),
        check('cpu_factory_deferred', "from gui.cpu_detail_panel import CPUDetailPanel" in main_src and "factory=factory" in main_src),
        check('ram_factory_deferred', "from gui.ram_detail_panel import RAMDetailPanel" in main_src),
        check('gpu_factory_deferred', "from gui.gpu_detail_panel import GPUDetailPanel" in main_src),
        check('storage_shell_first', storage_open.find("commit_internal_page(app, 'storage_details', host, panel=None)") < storage_open.find('panel = StorageDetailPanel(app, host, disk_index)')),
        check('storage_build_deferred', 'defer(build_panel, 16)' in storage_open or 'app.after(16, build_panel)' in storage_open),
        check('cpu_hidden_refresh_paused', 'def set_active(self, active):' in cpu and 'if self._alive and self._active:' in cpu),
        check('ram_hidden_refresh_paused', 'def set_active(self, active):' in ram and 'if self._alive and self._active:' in ram),
        check('gpu_hidden_refresh_paused', 'def set_active(self, active):' in gpu and 'if self._alive and self._active:' in gpu),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
