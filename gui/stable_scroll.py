"""Motor de scroll estable y reutilizable para las páginas internas de CorePulse.

V2 elimina el patrón ``Canvas.create_window`` con árboles grandes de widgets CTk.
En Windows ese patrón puede dejar artefactos/ghosting porque CustomTkinter dibuja
cada control sobre canvases propios mientras el canvas padre desplaza ventanas
embebidas. Esta implementación usa un viewport nativo que recorta un único frame
hijo movido con ``place``. Además agrupa eventos de rueda a ~60 FPS y difiere
repintados costosos hasta que termina la inercia.
"""
from __future__ import annotations
from core.theme_manager import color as theme_color

import time
import weakref
import tkinter as tk
import customtkinter as ctk

DEFAULT_BG = theme_color('#06111f')
DEFAULT_SCROLLBAR = theme_color('#31516d')
DEFAULT_SCROLLBAR_HOVER = theme_color(theme_color('#416887'))


class _WheelRouter:
    """Enruta la rueda sólo al StableScrollHost visible bajo el puntero."""

    _instances = weakref.WeakKeyDictionary()

    def __init__(self, root):
        self.root = root
        self.hosts = []
        try:
            root.bind_all('<MouseWheel>', self._dispatch, add='+')
            root.bind_all('<Button-4>', self._dispatch, add='+')
            root.bind_all('<Button-5>', self._dispatch, add='+')
        except Exception:
            pass

    @classmethod
    def for_widget(cls, widget):
        try:
            root = widget.winfo_toplevel()
        except Exception:
            return None
        router = cls._instances.get(root)
        if router is None:
            router = cls(root)
            cls._instances[root] = router
        return router

    def register(self, host):
        self.hosts = [ref for ref in self.hosts if ref() is not None and ref() is not host]
        self.hosts.append(weakref.ref(host))

    def unregister(self, host):
        self.hosts = [ref for ref in self.hosts if ref() is not None and ref() is not host]

    def _dispatch(self, event):
        try:
            x_root = int(getattr(event, 'x_root', self.root.winfo_pointerx()))
            y_root = int(getattr(event, 'y_root', self.root.winfo_pointery()))
        except Exception:
            return None
        for ref in reversed(self.hosts):
            host = ref()
            if host is None or not host._contains_root_point(x_root, y_root):
                continue
            return host._on_wheel(event)
        return None


class StableScrollHost(ctk.CTkFrame):
    """Viewport sin Canvas para listas/páginas CTk grandes.

    Cree los controles dentro de :attr:`content`. La API pública conserva
    ``is_scrolling()``, ``defer_until_idle()``, ``yview()`` y ``yview_moveto()``
    para que las vistas existentes no necesiten lógica específica.
    """

    def __init__(
        self,
        master,
        *,
        fg_color=DEFAULT_BG,
        scrollbar_button_color=DEFAULT_SCROLLBAR,
        scrollbar_button_hover_color=DEFAULT_SCROLLBAR_HOVER,
        scroll_hold_ms=360,
        wheel_pixels=58,
        **kwargs,
    ):
        kwargs.setdefault('corner_radius', 0)
        kwargs.setdefault('border_width', 0)
        super().__init__(master, fg_color=fg_color, **kwargs)
        self._bg = fg_color if isinstance(fg_color, str) and fg_color != 'transparent' else DEFAULT_BG
        self._scroll_hold = max(0.20, float(scroll_hold_ms) / 1000.0)
        self._wheel_pixels = max(18.0, float(wheel_pixels))
        self._scroll_active_until = 0.0
        self._destroyed = False

        self._offset = 0.0
        self._content_height = 1
        self._viewport_height = 1
        self._max_offset = 0.0
        self._pending_wheel_px = 0.0
        self._pending_moveto = None

        self._geometry_after = None
        self._motion_after = None
        self._idle_after = None
        self._idle_callbacks = []

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Un Frame Tk real actúa como región de clipping para todos sus hijos.
        # No existe create_window/canvas que deba mover decenas de sub-canvases.
        self.viewport = tk.Frame(self, bg=self._bg, bd=0, highlightthickness=0, relief='flat', takefocus=0)
        self.viewport.grid(row=0, column=0, sticky='nsew')
        self.viewport.grid_propagate(False)

        self.scrollbar = ctk.CTkScrollbar(
            self,
            orientation='vertical',
            command=self._scrollbar_command,
            fg_color=self._bg,
            button_color=scrollbar_button_color,
            button_hover_color=scrollbar_button_hover_color,
            width=12,
        )
        self.scrollbar.grid(row=0, column=1, sticky='ns', padx=(4, 0))

        self.content = ctk.CTkFrame(self.viewport, fg_color=self._bg, corner_radius=0, border_width=0)
        self.content.place(x=0, y=0, relwidth=1.0)

        self.content.bind('<Configure>', self._on_content_configure, add='+')
        self.viewport.bind('<Configure>', self._on_viewport_configure, add='+')
        self.bind('<Map>', lambda _e: self._schedule_geometry(1), add='+')

        self._router = _WheelRouter.for_widget(self)
        if self._router is not None:
            self._router.register(self)
        self._schedule_geometry(1)

    def _contains_root_point(self, x_root, y_root):
        if self._destroyed:
            return False
        try:
            if not self.winfo_exists() or not self.winfo_viewable():
                return False
            x0, y0 = self.winfo_rootx(), self.winfo_rooty()
            return x0 <= x_root < x0 + self.winfo_width() and y0 <= y_root < y0 + self.winfo_height()
        except Exception:
            return False

    def _mark_scrolling(self, hold=None):
        self._scroll_active_until = max(
            self._scroll_active_until,
            time.monotonic() + (self._scroll_hold if hold is None else float(hold)),
        )
        self._schedule_idle_flush()

    def is_scrolling(self):
        return time.monotonic() < self._scroll_active_until or self._motion_after is not None

    def _on_wheel(self, event):
        if self._destroyed or self._max_offset <= 0.5:
            return None
        delta = float(getattr(event, 'delta', 0) or 0)
        num = getattr(event, 'num', None)
        if num == 4:
            px = -self._wheel_pixels * 1.35
        elif num == 5:
            px = self._wheel_pixels * 1.35
        elif delta:
            # Delta proporcional conserva el gesto de touchpad; un notch de mouse
            # (120) equivale aproximadamente a wheel_pixels.
            px = (-delta / 120.0) * self._wheel_pixels
            if abs(px) < 5.0:
                px = -5.0 if delta > 0 else 5.0
        else:
            return None
        self._mark_scrolling()
        self._pending_wheel_px += px
        self._schedule_motion()
        return 'break'

    def _scrollbar_command(self, *args):
        if not args:
            return
        self._mark_scrolling(0.45)
        try:
            op = str(args[0])
            if op == 'moveto' and len(args) >= 2:
                self._pending_moveto = max(0.0, min(1.0, float(args[1])))
            elif op == 'scroll' and len(args) >= 3:
                amount = int(float(args[1]))
                unit = str(args[2])
                step = self._viewport_height * 0.86 if unit == 'pages' else self._wheel_pixels
                self._pending_wheel_px += amount * step
            else:
                # Compatibilidad defensiva con callbacks que entregan directamente
                # una fracción.
                self._pending_moveto = max(0.0, min(1.0, float(args[-1])))
        except Exception:
            return
        self._schedule_motion()

    def _schedule_motion(self):
        if self._destroyed or self._motion_after is not None:
            return
        try:
            self._motion_after = self.after(16, self._flush_motion)
        except Exception:
            self._motion_after = None

    def _flush_motion(self):
        self._motion_after = None
        if self._destroyed:
            return
        if self._pending_moveto is not None:
            self._offset = self._pending_moveto * self._max_offset
            self._pending_moveto = None
            self._pending_wheel_px = 0.0
        elif self._pending_wheel_px:
            self._offset += self._pending_wheel_px
            self._pending_wheel_px = 0.0
        self._apply_offset()

    def _apply_offset(self):
        self._offset = max(0.0, min(float(self._max_offset), float(self._offset)))
        try:
            self.content.place_configure(y=-int(round(self._offset)))
        except Exception:
            return
        self._sync_scrollbar()

    def _sync_scrollbar(self):
        try:
            if self._content_height <= self._viewport_height + 2:
                self.scrollbar.grid_remove()
                self.scrollbar.set(0.0, 1.0)
                return
            self.scrollbar.grid()
            total = max(1.0, float(self._content_height))
            first = max(0.0, min(1.0, self._offset / total))
            last = max(first, min(1.0, (self._offset + self._viewport_height) / total))
            self.scrollbar.set(first, last)
        except Exception:
            pass

    def _on_viewport_configure(self, _event=None):
        self._schedule_geometry(18)

    def _on_content_configure(self, _event=None):
        self._schedule_geometry(28)

    # Alias mantenidos para compatibilidad y para que los tests de builds previas
    # sigan representando el mismo contrato conceptual.
    def _schedule_scrollregion(self, delay_ms=28):
        self._schedule_geometry(delay_ms)

    def _refresh_scrollregion(self):
        self._refresh_geometry()

    def _schedule_geometry(self, delay_ms=28):
        if self._destroyed:
            return
        if self._geometry_after is not None:
            try:
                self.after_cancel(self._geometry_after)
            except Exception:
                pass
        try:
            self._geometry_after = self.after(int(delay_ms), self._refresh_geometry)
        except Exception:
            self._geometry_after = None

    def _refresh_geometry(self):
        self._geometry_after = None
        if self._destroyed:
            return
        if self.is_scrolling():
            self._schedule_geometry(90)
            return
        try:
            self.update_idletasks()
            viewport_h = max(1, int(self.viewport.winfo_height()))
            content_h = max(1, int(self.content.winfo_reqheight()))
            self._viewport_height = viewport_h
            self._content_height = content_h
            self._max_offset = max(0.0, float(content_h - viewport_h))
            self._offset = min(self._offset, self._max_offset)
            self._apply_offset()
        except Exception:
            pass

    def defer_until_idle(self, callback):
        if self._destroyed:
            return
        self._idle_callbacks.append(callback)
        self._schedule_idle_flush()

    def _schedule_idle_flush(self):
        if self._destroyed or self._idle_after is not None:
            return
        try:
            self._idle_after = self.after(72, self._flush_idle_callbacks)
        except Exception:
            self._idle_after = None

    def _flush_idle_callbacks(self):
        self._idle_after = None
        if self._destroyed:
            return
        if self.is_scrolling():
            self._schedule_idle_flush()
            return
        callbacks, self._idle_callbacks = self._idle_callbacks[-1:], []
        for callback in callbacks:
            try:
                callback()
            except Exception:
                pass
        self._schedule_geometry(1)

    def yview(self):
        if self._content_height <= self._viewport_height + 2:
            return (0.0, 1.0)
        total = max(1.0, float(self._content_height))
        first = max(0.0, min(1.0, self._offset / total))
        last = max(first, min(1.0, (self._offset + self._viewport_height) / total))
        return (first, last)

    def yview_moveto(self, fraction):
        try:
            self._pending_moveto = max(0.0, min(1.0, float(fraction)))
            self._mark_scrolling(0.20)
            self._schedule_motion()
        except Exception:
            pass

    def destroy(self):
        self._destroyed = True
        if self._router is not None:
            try:
                self._router.unregister(self)
            except Exception:
                pass
        for after_id in (self._geometry_after, self._motion_after, self._idle_after):
            if after_id is not None:
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
        self._idle_callbacks.clear()
        super().destroy()
