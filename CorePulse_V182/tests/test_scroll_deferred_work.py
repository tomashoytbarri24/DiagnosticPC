"""No perder finalizaciones ni acumular repintados durante scroll prolongado."""

import pytest
pytest.importorskip("customtkinter", reason="GUI dependency not installed in this validation environment")

import types
import unittest
from unittest.mock import Mock

from gui.stable_scroll import StableScrollHost


def host():
    obj = types.SimpleNamespace(_destroyed=False, _idle_callbacks={}, _idle_after=None,
                                after=Mock(return_value='idle'), is_scrolling=lambda: False,
                                _schedule_geometry=Mock())
    for name in ('defer_until_idle', '_schedule_idle_flush', '_flush_idle_callbacks'):
        setattr(obj, name, types.MethodType(getattr(StableScrollHost, name), obj))
    return obj


class DeferredWorkTests(unittest.TestCase):
    def test_detection_finish_survives_later_filter(self):
        obj = host()
        actions = []
        obj.defer_until_idle(lambda: actions.append('detection-finished'))
        obj.defer_until_idle(lambda: actions.append('filter'), key='filter')
        obj._flush_idle_callbacks()
        self.assertEqual(actions, ['detection-finished', 'filter'])

    def test_thousand_updates_keep_only_latest_payload_per_render(self):
        obj = host()
        actions = []
        for index in range(1000):
            obj.defer_until_idle(lambda i=index: actions.append(i), key='render')
        self.assertEqual(len(obj._idle_callbacks), 1)
        obj.after.assert_called_once()
        obj._flush_idle_callbacks()
        self.assertEqual(actions, [999])

    def test_independent_tasks_and_render_keys_are_all_retained(self):
        obj = host()
        actions = []
        for name, key in [('first', None), ('second', None), ('a', 'a'), ('b', 'b')]:
            obj.defer_until_idle(lambda n=name: actions.append(n), key=key)
        obj._flush_idle_callbacks()
        self.assertEqual(actions, ['first', 'second', 'a', 'b'])

    def test_still_scrolling_defers_without_dropping_work(self):
        obj = host()
        callback = Mock()
        obj.defer_until_idle(callback)
        obj.is_scrolling = lambda: True
        obj._flush_idle_callbacks()
        callback.assert_not_called()
        self.assertEqual(len(obj._idle_callbacks), 1)
        obj.is_scrolling = lambda: False
        obj._flush_idle_callbacks()
        callback.assert_called_once()

    def test_failing_task_does_not_discard_following_tasks(self):
        obj = host()
        callback = Mock()
        obj.defer_until_idle(Mock(side_effect=RuntimeError('test')))
        obj.defer_until_idle(callback)
        obj._flush_idle_callbacks()
        callback.assert_called_once()

    def test_task_queued_during_flush_runs_next_time(self):
        obj = host()
        later = Mock()
        obj.defer_until_idle(lambda: obj.defer_until_idle(later, key='render'))
        obj._flush_idle_callbacks()
        later.assert_not_called()
        obj._flush_idle_callbacks()
        later.assert_called_once()

    def test_destroy_during_callback_stops_remaining_work(self):
        obj = host()
        later = Mock()
        obj.defer_until_idle(lambda: setattr(obj, '_destroyed', True))
        obj.defer_until_idle(later)
        obj._flush_idle_callbacks()
        obj.defer_until_idle(later)
        later.assert_not_called()
        self.assertFalse(obj._idle_callbacks)


if __name__ == '__main__':
    unittest.main()
