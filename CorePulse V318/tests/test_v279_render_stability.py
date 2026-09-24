from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sidebar_hover_does_not_recursively_bind_children_or_unmap_close_control():
    source = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    block = source[source.index('def _install_sidebar_hover_close'):source.index('def _sync_sidebar_visibility_controls')]
    assert 'def bind_node' not in block
    assert 'action.place_forget' not in block
    assert "root.after(90" in block
    assert "root.bind('<Enter>', enter)" in block
    assert "add='+'" not in block
    assert "action.place(relx=1.0" in block


def test_benchmark_uses_two_phase_navigation_commit():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    nav = (ROOT / 'gui' / 'internal_navigation.py').read_text(encoding='utf-8')
    bench = (ROOT / 'gui' / 'benchmark_panel.py').read_text(encoding='utf-8')
    assert "stage_internal_page(self, 'benchmark', host, panel)" in main
    assert 'def stage_internal_page' in nav
    assert "self.after(16, publish_benchmark)" in main
    assert 'def prepare_for_commit' in bench
    assert 'staging.place(x=-20000' in bench
