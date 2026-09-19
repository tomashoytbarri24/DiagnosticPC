from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_v144_version_stage():
    ns = {}
    exec((ROOT / 'core' / 'version.py').read_text(encoding='utf-8'), ns)
    assert str(ns["VERSION"]).isdigit()
    assert bool(ns["STAGE"])


def test_health_center_accepts_initial_destination():
    src = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    assert 'initial_tab=None' in src
    assert 'initial_windows_section=None' in src
    assert 'def navigate_to(self, key=' in src
    assert "self._windows_section = (" in src


def test_main_opens_health_center_with_direct_target():
    src = (ROOT / 'main.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'App')
    fn = next(node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'open_health_center')
    segment = ast.get_source_segment(src, fn)
    assert "def open_health_center(self, tab='summary', windows_section=None)" in segment
    assert 'initial_tab=target_tab' in segment
    assert 'initial_windows_section=target_section' in segment
    assert 'prepared_panel.navigate_to(target_tab, target_section)' in segment


def test_diagnostic_no_longer_steps_through_views_with_after_callbacks():
    src = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'DiagnosticExperiencePanel')
    fn = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '_open_health_area')
    segment = ast.get_source_segment(src, fn)
    assert 'opener(tab=tab, windows_section=windows_section)' in segment
    assert 'attempts' not in segment
    assert '.after(' not in segment
    assert '_select_tab' not in segment
    assert '_set_windows_section' not in segment


def test_complete_diagnostic_policy_stays_v144_and_no_auto_repairs():
    src = (ROOT / 'core' / 'complete_diagnostic.py').read_text(encoding='utf-8')
    assert "'version': '2.0-v144'" in src
    assert "'stress_and_benchmark_are_distinct': True" in src
    assert "'automatic_repairs': False" in src



def test_navigate_to_sets_final_state_before_single_render_call():
    src = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'HealthCenterPanel')
    fn = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'navigate_to')
    segment = ast.get_source_segment(src, fn)
    assert segment.count('self._render()') == 1
    assert segment.index('self._tab = target') < segment.index('self._render()')
    assert segment.index('self._windows_section = target_section') < segment.index('self._render()')
