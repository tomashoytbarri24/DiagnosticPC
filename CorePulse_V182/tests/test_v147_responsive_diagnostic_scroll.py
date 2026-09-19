from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v147_version_stage():
    ns = {}
    exec((ROOT / 'core' / 'version.py').read_text(encoding='utf-8'), ns)
    assert str(ns["VERSION"]).isdigit()
    assert bool(ns["STAGE"])


def test_diagnostic_uses_stable_fast_scroll_not_ctk_scrollable_frame():
    src = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert 'from gui.stable_scroll import StableScrollHost' in src
    assert 'self.details_scroll = StableScrollHost(' in src
    assert 'wheel_pixels=96' in src
    assert 'CTkScrollableFrame' not in src


def test_result_has_responsive_breakpoints_and_one_column_fallback():
    src = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert "if width >= 1180:" in src
    assert "elif width >= 900:" in src
    assert "columns = 1 if width < 830 else 2" in src
    assert "height < 660" in src


def test_component_cards_are_compact_but_all_six_remain():
    src = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert "('cpu', 'gpu', 'ram', 'storage', 'battery', 'windows')" in src
    assert "text='Ver detalle', height=24" in src
    assert "evidence[:2]" in src
    assert "evidence_text[:147]" in src


def test_result_scrolls_to_top_when_final_report_is_shown():
    src = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert 'self.details_scroll.yview_moveto(0.0)' in src


def test_v147_does_not_change_diagnostic_truth_policy():
    src = (ROOT / 'core' / 'complete_diagnostic.py').read_text(encoding='utf-8')
    assert "'real_or_na': True" in src
    assert "'stress_and_benchmark_are_distinct': True" in src
    assert "'automatic_repairs': False" in src
