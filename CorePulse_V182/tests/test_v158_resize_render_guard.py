"""V158 — Guarda de redibujo CTk durante resize continuo.

Sigue el mismo patrón que tests/test_v148_fluid_resize_diagnostic.py y
tests/test_v157_diagnostic_lifecycle.py: aserciones estáticas sobre el
código fuente (no requieren Tcl/Tk) más una clase de widgets reales que se
omite si Tcl/Tk no está disponible en el entorno de ejecución.
"""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


class SourceContractTests(unittest.TestCase):
    def test_v158_version_stage(self):
        from core.version import VERSION
        self.assertGreaterEqual(int(VERSION), 158)

    def test_guard_module_exists_and_is_reentrant(self):
        src = read('gui/resize_render_guard.py')
        self.assertIn('def install():', src)
        self.assertIn('def set_active(active, *, owner=None):', src)
        self.assertIn('def flush(*, owner=None):', src)
        # Idempotente: instalar dos veces no debe re-parchear ni fallar.
        self.assertIn('_corepulse_resize_guard_installed', src)

    def test_guard_installed_before_any_other_gui_import(self):
        src = read('main.py')
        install_pos = src.index('_install_resize_render_guard()')
        ctk_import_pos = src.index('import customtkinter as ctk')
        first_gui_import_pos = src.index('from gui.dashboard import')
        self.assertLess(ctk_import_pos, install_pos)
        self.assertLess(install_pos, first_gui_import_pos)

    def test_dashboard_layout_routes_is_resizing_through_guard(self):
        src = read('gui/dashboard_layout.py')
        self.assertIn('def _set_resizing(app, active):', src)
        self.assertIn('_set_render_guard_active(active, owner=app)', src)
        # Ninguna asignación directa a app.is_resizing debe quedar fuera de
        # _set_resizing (salvo la propia definición dentro de la función).
        direct_assignments = src.count('app.is_resizing = ')
        self.assertEqual(direct_assignments, 1)  # sólo dentro de _set_resizing

    def test_v148_debounce_untouched(self):
        # El fix de V158 es un complemento, no un reemplazo: el detector
        # trailing de V148 sigue intacto.
        src = read('gui/dashboard_layout.py')
        self.assertIn("if getattr(app, '_resize_after_id', None) is None:", src)
        self.assertIn('RESIZE_DEBOUNCE_MS', src)


class RealWidgetGuardTests(unittest.TestCase):
    def setUp(self):
        import tkinter
        import customtkinter as ctk
        try:
            self.root = ctk.CTk()
        except tkinter.TclError as exc:
            self.skipTest('Tcl/Tk no disponible en el entorno: ' + str(exc).splitlines()[0])
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_redraw_is_coalesced_during_active_resize_and_flushed_once(self):
        import gui.resize_render_guard as guard
        import customtkinter as ctk
        guard.install()
        guard.set_active(False)  # estado limpio entre pruebas

        frame = ctk.CTkFrame(self.root, fg_color='#202020', corner_radius=12)
        frame.pack(fill='both', expand=True)
        self.root.update_idletasks()

        # Un root retirado puede no emitir Configure al cambiar geometry.
        # Entregar dos eventos al widget real permite contar dibujos sin que
        # la prueba pase vacíamente con cero cambios de tamaño.
        guard.set_active(True, owner=self.root)
        with patch.object(frame, '_draw', wraps=frame._draw) as draw:
            try:
                frame._update_dimensions_event(SimpleNamespace(width=120, height=80))
                frame._update_dimensions_event(SimpleNamespace(width=160, height=90))
                self.assertEqual(draw.call_count, 0)
                self.assertEqual(guard.pending_count(), 1)
            finally:
                guard.set_active(False, owner=self.root)
            self.assertEqual(draw.call_count, 1)
            self.assertEqual(frame._current_width, frame._reverse_widget_scaling(160))
            self.assertEqual(frame._current_height, frame._reverse_widget_scaling(90))
        # Al desactivar, la cola queda vacía (se aplicó una sola vez).
        self.assertEqual(guard.pending_count(), 0)
        self.assertFalse(guard.is_active())

    def test_destroyed_widget_during_resize_does_not_raise_on_flush(self):
        import gui.resize_render_guard as guard
        import customtkinter as ctk
        guard.install()
        guard.set_active(False)

        frame = ctk.CTkFrame(self.root, fg_color='#202020', corner_radius=12)
        frame.pack(fill='both', expand=True)
        button = ctk.CTkButton(frame, text='hola')
        button.pack()
        self.root.update_idletasks()

        guard.set_active(True)
        self.root.geometry('700x520')
        self.root.update_idletasks()
        button.destroy()
        # No debe lanzar excepción aunque un widget pendiente ya no exista.
        guard.set_active(False)
        self.assertEqual(guard.pending_count(), 0)

    def test_diagnostic_lifecycle_unaffected_by_guard_active_state(self):
        # Preservación explícita del punto 1 de la solicitud V158: el ciclo
        # de vida del Diagnóstico Completo (token propio por sesión,
        # cancelación, reinicio) no debe verse afectado por que la guarda de
        # redibujo esté activa durante un resize simultáneo.
        import gui.resize_render_guard as guard
        from core.diagnostic_lifecycle import DiagnosticRun, DiagnosticState
        guard.install()
        guard.set_active(True)
        try:
            run_a = DiagnosticRun(token=1)
            self.assertTrue(run_a.transition(DiagnosticState.RUNNING_BASELINE))
            self.assertTrue(run_a.cancel())
            self.assertEqual(run_a.state, DiagnosticState.CANCELLED)
            # Iniciar → Cancelar → volver a iniciar: la sesión anterior queda
            # cerrada y una nueva sesión (token distinto) puede arrancar de
            # inmediato, exactamente igual que sin la guarda activa.
            run_b = DiagnosticRun(token=2)
            self.assertTrue(run_b.transition(DiagnosticState.RUNNING_BASELINE))
            self.assertEqual(run_b.state, DiagnosticState.RUNNING_BASELINE)
            self.assertNotEqual(run_a.token, run_b.token)
        finally:
            guard.set_active(False)


if __name__ == '__main__':
    unittest.main()
