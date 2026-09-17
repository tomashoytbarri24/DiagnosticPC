"""Ejecuta métodos reales del App sin importar sensores ni abrir Tk.

Matplotlib Agg permite comprobar datos, ejes y recuperación del fondo.
No mide fluidez del escritorio ni velocidad del hardware.
"""
import ast
import math
from pathlib import Path
import threading
import types
import unittest
from unittest.mock import Mock

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

ROOT = Path(__file__).resolve().parents[1]


def methods(path, class_name, names):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    selected = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    scope = {'math': math}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), scope)
    return {name: scope[name] for name in names}


class ChartTests(unittest.TestCase):
    def setUp(self):
        self.app = app = types.SimpleNamespace(
            is_running=True, _charts_ready=True, is_resizing=False,
            _active_internal_page=None, winfo_viewable=lambda: True,
            telemetry_lock=threading.Lock(), max_points=60,
            cpu_history=[10., 20.], ram_history=[30., 40.], gpu_history=[float('nan'), 5.],
            _chart_history_revision=1, background=None, after=Mock(return_value='next'))
        app.fig = Figure(figsize=(6, 2))
        app.canvas = FigureCanvasAgg(app.fig)
        app.canvas.blit = Mock(wraps=app.canvas.blit)
        app.canvas.draw_idle = Mock(wraps=app.canvas.draw_idle)
        for name, ax in zip(('cpu', 'ram', 'gpu'), app.fig.subplots(1, 3)):
            setattr(app, 'ax_' + name, ax)
            setattr(app, 'line_' + name, ax.plot([], [], animated=True)[0])
        for name, fn in methods(ROOT / 'main.py', 'App', (
            '_chart_series_for_display', '_trend_tick_labels_for_count',
            '_refresh_trend_axis_labels', 'on_draw', 'update_charts_fast')).items():
            setattr(app, name, types.MethodType(fn, app))
        app.canvas.mpl_connect('draw_event', app.on_draw)

    def test_repeated_ticks_draw_once_until_new_sample(self):
        app = self.app
        for _ in range(100):
            app.update_charts_fast()
        self.assertEqual(app.canvas.draw_idle.call_count, 1)
        self.assertEqual(app.canvas.blit.call_count, 1)
        self.assertEqual(app.after.call_count, 100)
        app.cpu_history[-1] = 27.
        app._chart_history_revision += 1
        app.update_charts_fast()
        self.assertEqual(app.canvas.blit.call_count, 2)
        self.assertEqual(list(app.line_cpu.get_ydata()), [10., 27.])

    def test_hidden_and_resize_skip_drawing_but_resume_latest_data(self):
        app = self.app
        for flag in ('_active_internal_page', 'is_resizing'):
            setattr(app, flag, True)
            app.update_charts_fast()
            setattr(app, flag, False)
        app.winfo_viewable = lambda: False
        app.update_charts_fast()
        self.assertEqual(app.canvas.draw_idle.call_count, 0)
        app.cpu_history[-1] = 45.
        app._chart_history_revision += 1
        app.winfo_viewable = lambda: True
        app.update_charts_fast()
        self.assertEqual(list(app.line_cpu.get_ydata()), [10., 45.])

    def test_resize_invalidated_background_is_restored_without_new_sample(self):
        app = self.app
        app.update_charts_fast()
        app.background = None
        app.update_charts_fast()
        self.assertEqual(app.canvas.draw_idle.call_count, 2)
        self.assertIsNotNone(app.background)

    def test_axis_changes_redraw_labels_and_na_stays_na(self):
        app = self.app
        app.cpu_history = [float('nan')] * 60
        app.ram_history = [float('nan')] * 60
        app.gpu_history = [float('nan')] * 60
        app.update_charts_fast()
        self.assertTrue(all(math.isnan(v) for v in app.line_cpu.get_ydata()))
        app.cpu_history = [10.] * 60
        app._chart_history_revision += 1
        app.update_charts_fast()
        self.assertEqual(app.canvas.draw_idle.call_count, 2)
        self.assertEqual(app.ax_cpu.get_xticklabels()[0].get_text(), '-60s')

    def test_failed_render_can_retry_same_revision(self):
        app = self.app
        original = app.line_cpu.set_data
        app.line_cpu.set_data = Mock(side_effect=RuntimeError('transient'))
        app.update_charts_fast()
        app.line_cpu.set_data = original
        app.update_charts_fast()
        self.assertEqual(list(app.line_cpu.get_ydata()), [10., 20.])
        self.assertIsNotNone(app.background)


class GamingLifecycleTests(unittest.TestCase):
    def test_cached_page_forwards_visibility_and_refresh(self):
        app = types.SimpleNamespace(_visible=True, _alive=True,
            _child_panel=types.SimpleNamespace(set_active=Mock(), refresh=Mock()))
        for name, fn in methods(ROOT / 'gui/gaming_panel.py', 'GamingPanel',
                                ('_set_panel_active', 'set_active', 'refresh')).items():
            setattr(app, name, types.MethodType(fn, app))
        app.set_active(False)
        app.set_active(True)
        app.refresh()
        self.assertEqual([c.args[0] for c in app._child_panel.set_active.call_args_list], [False, True])
        app._child_panel.refresh.assert_called_once()


if __name__ == '__main__':
    unittest.main()
