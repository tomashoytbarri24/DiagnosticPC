from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_v142_version_and_stage():
    ns = {}
    exec((ROOT / 'core' / 'version.py').read_text(encoding='utf-8'), ns)
    assert str(ns["VERSION"]).isdigit()
    assert bool(ns["STAGE"])


def test_complete_diagnostic_has_distinct_stress_and_benchmark_phases():
    src = (ROOT / 'core' / 'complete_diagnostic.py').read_text(encoding='utf-8')
    assert 'def run_stress_suite' in src
    assert 'def run_complete_diagnostic' in src
    assert "'stress_and_benchmark_are_distinct': True" in src
    assert "'stress_publishes_performance_score': False" in src
    assert "'benchmark_has_external_ranking': False" in src
    assert "'automatic_repairs': False" in src
    assert 'run_benchmark_suite(' in src


def test_stress_does_not_expose_benchmark_value_as_score():
    src = (ROOT / 'core' / 'complete_diagnostic.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_stress_component')
    segment = ast.get_source_segment(src, fn)
    assert "'performance_score_used': False" in segment
    assert "'value':" not in segment


def test_main_maps_baseline_then_runs_complete_worker():
    src = (ROOT / 'main.py').read_text(encoding='utf-8')
    section = src[src.index('    # V142: un solo botón'):src.index('    # Exporta exactamente la evidencia congelada')]
    assert "* 0.22" in section
    assert 'run_complete_diagnostic' in section
    assert 'CorePulse-CompleteDiagnostic' in section
    assert "text='Generar PDF · opcional'" in section


def test_diagnostic_ui_exposes_single_complete_flow():
    src = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert 'def update_complete_progress' in src
    assert "text='Diagnóstico completo'" in src
    assert 'Escritorio → Windows → estrés → benchmark → resultado.' in src
    assert 'Las herramientas de reparación siguen separadas.' in src


def test_pdf_includes_complete_diagnostic_section():
    src = (ROOT / 'core' / 'report_builder.py').read_text(encoding='utf-8')
    assert 'def _complete_diagnostic_flowables' in src
    assert "'3.1 Diagnóstico Completo 2.0'" in src
    assert 'La prueba de estrés evalúa estabilidad bajo carga' in src


def test_protected_runtime_and_nvme_files_not_imported_by_new_orchestrator():
    src = (ROOT / 'core' / 'complete_diagnostic.py').read_text(encoding='utf-8')
    assert 'runtime_venv_path' not in src
    assert 'source_runtime_bootstrap' not in src
    assert 'nvme_smart_windows' not in src
