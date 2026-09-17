from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_v143_version_stage():
    ns = {}
    exec((ROOT / 'core' / 'version.py').read_text(encoding='utf-8'), ns)
    assert ns['VERSION'] == '143'
    assert ns['STAGE'] == 'COMPLETE_DIAGNOSTIC_ACTIONABLE_REPORT'


def test_result_ui_is_component_first():
    src = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert 'def _component_reports' in src
    assert "('cpu', 'gpu', 'ram', 'storage', 'battery', 'windows')" in src
    assert "self.lbl_details_title.configure(text='ESTADO POR COMPONENTE'" in src
    assert 'def _show_component_report' in src


def test_component_report_does_not_create_score():
    src = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_component_reports')
    segment = ast.get_source_segment(src, fn)
    assert 'score =' not in segment
    assert "'score'" not in segment
    assert "'health_score'" not in segment
    assert 'Benchmark' in segment


def test_actions_are_navigation_only():
    src = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert "getattr(self.app, 'open_cpu_details'" in src
    assert "getattr(self.app, 'open_gpu_details'" in src
    assert "getattr(self.app, 'open_ram_details'" in src
    assert "getattr(self.app, 'open_storage_details'" in src
    assert "self._open_health_area('battery')" in src
    assert "self._open_health_area('windows', section)" in src
    assert 'repair_windows' not in src


def test_v143_keeps_complete_diagnostic_policy():
    src = (ROOT / 'core' / 'complete_diagnostic.py').read_text(encoding='utf-8')
    assert "'stress_and_benchmark_are_distinct': True" in src
    assert "'automatic_repairs': False" in src
    assert "'benchmark_has_external_ranking': False" in src
    assert "'version': '2.0-v143'" in src
