"""Pruebas de comportamiento del guard con el manejador CTk instalado.

Se usa el manejador real de dimensiones con widgets instrumentados, sin display.
No representan una medición de fluidez ni arrastre físico en Windows.
"""
import gc
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

ROOT = Path(__file__).resolve().parents[1]


def fresh_guard():
    spec = importlib.util.spec_from_file_location('isolated_resize_guard', ROOT/'gui/resize_render_guard.py')
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    return guard


class Window:
    pass


class Widget:
    def __init__(self, owner, scale=1):
        self.owner = owner
        self.scale = scale
        self._current_width = self._current_height = 0
        self.exists = True
        self.draws = []
    def winfo_toplevel(self):
        return self.owner
    def winfo_exists(self):
        return self.exists
    def _reverse_widget_scaling(self, value):
        return value/self.scale
    def _draw(self, *args, **kwargs):
        self.draws.append((self._current_width, self._current_height, args, kwargs))


class ResizeOwnershipTests(unittest.TestCase):
    def setUp(self):
        from customtkinter.windows.widgets.core_widget_classes.ctk_base_class import CTkBaseClass
        self.original = getattr(CTkBaseClass, '_corepulse_resize_guard_original', CTkBaseClass._update_dimensions_event)
        self.guard = fresh_guard()
        self.guard._original_update_dimensions_event = self.original
        self.main = Window()
        self.other = Window()

    def resize(self, widget, width, height=50):
        return self.guard._patched_update_dimensions_event(widget, SimpleNamespace(width=width, height=height))

    def test_inactive_preserves_original_side_effects_return_and_draw(self):
        calls=[]
        def original(widget,event):
            calls.append(event)
            self.original(widget,event)
            return 'original return'
        self.guard._original_update_dimensions_event = original
        widget=Widget(self.main)
        self.assertEqual(self.resize(widget,100), 'original return')
        self.assertEqual(len(calls),1)
        self.assertEqual(len(widget.draws),1)

    def test_thousand_events_produce_one_draw_at_final_size(self):
        widget=Widget(self.main)
        self.guard.set_active(True,owner=self.main)
        for width in range(100,1100):
            self.resize(widget,width)
        self.assertEqual(widget._current_width,1099)
        self.assertEqual(widget.draws,[])
        self.assertEqual(self.guard.pending_count(),1)
        self.guard.set_active(False,owner=self.main)
        self.assertEqual(len(widget.draws),1)
        self.assertEqual(widget.draws[0][:2],(1099,50))
        self.assertEqual(widget.draws[0][3],{'no_color_updates':True})
        self.guard.flush()
        self.assertEqual(len(widget.draws),1)

    def test_unchanged_size_does_not_queue_or_draw(self):
        widget=Widget(self.main)
        self.resize(widget,100)
        self.guard.set_active(True,owner=self.main)
        self.resize(widget,100)
        self.assertEqual(self.guard.pending_count(),0)
        self.guard.set_active(False,owner=self.main)
        self.assertEqual(len(widget.draws),1)

    def test_other_toplevel_draws_immediately(self):
        main,dialog=Widget(self.main),Widget(self.other)
        self.guard.set_active(True,owner=self.main)
        self.resize(main,100)
        self.resize(dialog,200)
        self.assertEqual(len(main.draws),0)
        self.assertEqual(len(dialog.draws),1)
        self.assertEqual(self.guard.pending_count(),1)

    def test_two_owners_finish_independently(self):
        main,other=Widget(self.main),Widget(self.other)
        for owner in (self.main,self.other):
            self.guard.set_active(True,owner=owner)
        self.resize(main,100)
        self.resize(other,200)
        self.guard.set_active(False,owner=self.main)
        self.assertEqual(len(main.draws),1)
        self.assertEqual(len(other.draws),0)
        self.assertTrue(self.guard.is_active(self.other))
        self.guard.set_active(False,owner=self.other)
        self.assertEqual(len(other.draws),1)
        self.assertFalse(self.guard.is_active())

    def test_dpi_conversion_matches_original(self):
        for scale in (1,1.25,1.5,2):
            with self.subTest(scale=scale):
                deferred=Widget(self.main,scale)
                reference=Widget(self.other,scale)
                self.guard.set_active(True,owner=self.main)
                for width in (113,127,128,150):
                    self.resize(deferred,width,77)
                    self.original(reference,SimpleNamespace(width=width,height=77))
                self.guard.set_active(False,owner=self.main)
                self.assertEqual(deferred.draws[-1],reference.draws[-1])
                self.assertEqual(len(deferred.draws),1)

    def test_destroyed_pending_widget_does_not_block_others(self):
        gone,live=Widget(self.main),Widget(self.main)
        self.guard.set_active(True,owner=self.main)
        self.resize(gone,100)
        self.resize(live,100)
        gone.exists=False
        self.guard.set_active(False,owner=self.main)
        self.assertEqual(gone.draws,[])
        self.assertEqual(len(live.draws),1)
        self.assertEqual(self.guard.pending_count(),0)

    def test_failed_draw_does_not_leave_other_widgets_frozen(self):
        bad,good=Widget(self.main),Widget(self.main)
        self.guard.set_active(True,owner=self.main)
        self.resize(bad,100)
        self.resize(good,100)
        def fail(**kwargs):
            raise RuntimeError('destroyed canvas')
        bad._draw=fail
        self.guard.set_active(False,owner=self.main)
        self.assertEqual(len(good.draws),1)
        self.assertEqual(self.guard.pending_count(),0)

    def test_shutdown_release_drops_owned_work_without_drawing(self):
        widget=Widget(self.main)
        self.guard.set_active(True,owner=self.main)
        self.resize(widget,100)
        self.guard.release(self.main)
        self.assertEqual(widget.draws,[])
        self.assertEqual(self.guard.pending_count(),0)
        self.assertFalse(self.guard.is_active())
        self.resize(widget,101)
        self.assertEqual(len(widget.draws),1)

    def test_instance_draw_override_restored_even_on_error(self):
        widget=Widget(self.main)
        draw=lambda **kwargs: None
        widget._draw=draw
        self.guard.set_active(True,owner=self.main)
        def fail(widget,event):
            raise ValueError('provider error')
        self.guard._original_update_dimensions_event=fail
        with self.assertRaises(ValueError):
            self.resize(widget,100)
        self.assertIs(widget._draw,draw)

    def test_class_draw_restored_after_original_error(self):
        widget=Widget(self.main)
        self.guard.set_active(True,owner=self.main)
        self.guard._original_update_dimensions_event=lambda *a: 1/0
        with self.assertRaises(ZeroDivisionError):
            self.resize(widget,100)
        self.assertNotIn('_draw',vars(widget))

    def test_dirty_queue_does_not_keep_destroyed_objects_alive(self):
        widget=Widget(self.main)
        self.guard.set_active(True,owner=self.main)
        self.resize(widget,100)
        reference=weakref.ref(widget)
        del widget
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(self.guard.pending_count(),0)

    def test_install_repeated_or_reloaded_keeps_one_original(self):
        class Base:
            _update_dimensions_event=self.original
        initial=Base._update_dimensions_event
        with patch.object(self.guard,'_resolve_base_class',return_value=Base):
            self.assertTrue(self.guard.install())
            self.assertTrue(self.guard.install())
        second=fresh_guard()
        with patch.object(second,'_resolve_base_class',return_value=Base):
            self.assertTrue(second.install())
        self.assertIs(second._original_update_dimensions_event,initial)
        self.assertIs(Base._update_dimensions_event,second._patched_update_dimensions_event)

    def test_unsupported_provider_returns_false_without_mutation(self):
        class Unsupported:
            pass
        with patch.object(self.guard,'_resolve_base_class',return_value=Unsupported):
            self.assertFalse(self.guard.install())
        self.assertFalse(hasattr(Unsupported,'_corepulse_resize_guard_installed'))

    def test_legacy_set_active_still_flushes_exactly_once(self):
        widget=Widget(self.main)
        self.guard.set_active(True)
        self.guard.set_active(True)
        self.resize(widget,100)
        self.guard.set_active(False)
        self.guard.set_active(False)
        self.assertEqual(len(widget.draws),1)
        self.assertFalse(self.guard.is_active())


if __name__=='__main__':
    unittest.main()
