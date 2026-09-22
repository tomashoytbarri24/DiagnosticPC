"""Regresión de callbacks y presentación, sin Tk ni hardware simulado como resultado."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class Widget:
    created = []

    def __init__(self, *args, **kwargs):
        self.options = kwargs
        self.value = None
        self.created.append(self)

    def pack(self, **kwargs): pass
    def grid(self, **kwargs): pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def winfo_exists(self): return True
    def configure(self, **kwargs): self.options.update(kwargs)
    def set(self, value): self.value = value
    def insert(self, index, value): self.value = value


def panel_class():
    source = Path(__file__).resolve().parents[1] / 'gui' / 'health_center_panel.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    original = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'HealthCenterPanel')
    methods = {'_set_visual_benchmark_progress', '_accept_visual_benchmark_progress',
               '_render_visual_benchmark_card', '_render_visual_benchmark_result_body',
               '_copy_benchmark_result_path'}
    original.body = [n for n in original.body if isinstance(n, ast.FunctionDef) and n.name in methods]
    namespace = {name: name for name in ('PURPLE', 'GREEN', 'TEXT2', 'MUTED', 'FONT', 'AMBER')}
    namespace.update(ctk=SimpleNamespace(**{name: Widget for name in
                     ('CTkFrame', 'CTkLabel', 'CTkProgressBar', 'CTkEntry', 'CTkButton')}),
                     theme_color=lambda value: value)
    exec(compile(ast.Module(body=[original], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['HealthCenterPanel']


class FinalStateTests(unittest.TestCase):
    def setUp(self):
        Widget.created = []
        self.panel = panel_class()()
        self.panel._alive = True
        self.panel._visual_benchmark_run_id = 2
        self.panel._visual_benchmark_finished = False
        self.panel._jobs = set()
        self.panel._visual_bench = None
        self.panel.visual_bench_progress_bar = Widget()
        self.panel.lbl_visual_bench_progress = Widget()
        self.panel.lbl_visual_bench_detail = Widget()

    def test_late_progress_cannot_replace_completion(self):
        p = self.panel
        p._accept_visual_benchmark_progress(2, .97, 'SSD', 'Estado OK')
        self.assertEqual(p.visual_bench_progress_bar.value, .97)
        p._visual_benchmark_finished = True
        p._set_visual_benchmark_progress(1, 'Benchmark completado', 'Ruta final')
        p._accept_visual_benchmark_progress(2, .97, 'SSD', 'Estado OK')
        self.assertEqual(p.visual_bench_progress_bar.value, 1)
        self.assertEqual(p.lbl_visual_bench_progress.options['text'], '100% · Benchmark completado')
        self.assertEqual(p.lbl_visual_bench_detail.options['text'], 'Ruta final')

    def test_previous_run_callback_is_ignored(self):
        p = self.panel
        p._set_visual_benchmark_progress(.1, 'Nueva prueba', '')
        p._accept_visual_benchmark_progress(1, 1, 'Anterior', '')
        self.assertEqual(p._visual_benchmark_progress, .1)

    def test_render_keeps_completion_and_copyable_path(self):
        p = self.panel
        path = r'C:\Carpeta con espacios\resultados\benchmark_gpu_v12_ultimo_resultado.json'
        p._visual_bench = {'status': 'OK', 'selected_components': [],
                           'system_suite': {'gpu_result_saved': True, 'gpu_result_path': path}}
        p._set_visual_benchmark_progress(1, 'Benchmark completado', 'Resultado GPU guardado en: ' + path)
        p._render_visual_benchmark_card(None)
        self.assertEqual(p.lbl_visual_bench_progress.options['text'], '100% · Benchmark completado')
        self.assertIn(path, p.lbl_visual_bench_detail.options['text'])
        self.assertTrue(any(w.value == path and w.options.get('state') == 'readonly' for w in Widget.created))
        self.assertTrue(any(w.options.get('text') == 'Copiar ruta' for w in Widget.created))

    def test_save_failure_is_visible(self):
        p = self.panel
        p._visual_bench = {'status': 'OK', 'selected_components': [],
                           'system_suite': {'gpu_result_saved': False, 'gpu_result_save_error': 'PermissionError'}}
        p._set_visual_benchmark_progress(1, 'Benchmark completado', '')
        p._render_visual_benchmark_card(None)
        self.assertTrue(any('PermissionError' in w.options.get('text', '') for w in Widget.created))


if __name__ == '__main__':
    unittest.main()
