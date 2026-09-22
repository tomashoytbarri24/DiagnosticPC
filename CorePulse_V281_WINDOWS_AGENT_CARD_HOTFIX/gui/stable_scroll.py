"""Scroll estable y reutilizable para las vistas internas de CorePulse.

V5 añade un backend de viewport por ``place`` para páginas CTk densas y conserva
la corrección V4 para el ghosting observado al *agarrar y arrastrar* la barra
de desplazamiento en Windows. El backend histórico sigue usando ``tk.Canvas``;
el backend ``place`` recorta un único frame hijo dentro de un viewport normal,
evitando el desfase de pintura entre ``Canvas.create_window`` y widgets CTk.
La barra continúa siendo propia de CorePulse y coalesce el drag por frame.

Principios:
- rueda/touchpad: desplazamiento directo del Canvas, sin interpolar el árbol;
- drag del thumb: coalescido a la cadencia visual (8-16 ms) y 1:1 por frame;
- durante drag no se recalcula ``scrollregion`` ni se reconstruyen vistas caras;
- al finalizar drag se aplica el último destino, se recalcula geometría una vez
  y se fuerza un repaint limpio;
- fuera de Windows el mismo contrato funciona sólo con primitivas Tk.
"""
from __future__ import annotations

import sys
import time
import weakref
import tkinter as tk
import customtkinter as ctk

from core.theme_manager import color as theme_color
from gui.high_refresh import get_ui_refresh_policy

DEFAULT_BG = theme_color('#06111f')
DEFAULT_SCROLLBAR = theme_color('#31516d')
DEFAULT_SCROLLBAR_HOVER = theme_color('#416887')
DEFAULT_SCROLLBAR_TRACK = theme_color('#0f172a')


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


class _CorePulseDragScrollbar(tk.Canvas):
    """Scrollbar vertical dibujado por CorePulse.

    CTkScrollbar actualiza su thumb en una capa distinta a la ventana embebida
    del ``Canvas``. En páginas densas eso permitía que el puntero avanzase varios
    eventos mientras Windows todavía estaba pintando el contenido anterior.
    Esta barra coalesce el drag a un único destino por frame y entrega el
    ``moveto`` al viewport antes de redibujar el thumb confirmado por ``set``.
    """

    def __init__(
        self,
        master,
        *,
        command,
        on_drag_start=None,
        on_drag_end=None,
        frame_ms=8,
        bg=DEFAULT_BG,
        track_color=DEFAULT_SCROLLBAR_TRACK,
        thumb_color=DEFAULT_SCROLLBAR,
        thumb_hover_color=DEFAULT_SCROLLBAR_HOVER,
        width=12,
        min_thumb_px=30,
    ):
        super().__init__(
            master,
            width=int(width),
            bg=bg,
            bd=0,
            relief='flat',
            highlightthickness=0,
            takefocus=0,
            cursor='arrow',
        )
        self._command = command
        self._on_drag_start = on_drag_start
        self._on_drag_end = on_drag_end
        self._frame_ms = max(8, int(frame_ms))
        self._track_color = track_color
        self._thumb_color = thumb_color
        self._thumb_hover_color = thumb_hover_color
        self._min_thumb_px = max(18, int(min_thumb_px))

        self._first = 0.0
        self._last = 1.0
        self._dragging = False
        self._hover = False
        self._drag_grip_y = 0.0
        self._pending_fraction = None
        self._drag_after = None
        self._last_drag_frame = 0.0
        self._thumb_bounds = (2, 2, max(3, int(width) - 2), 3)

        self.bind('<Configure>', self._on_configure, add='+')
        self.bind('<Motion>', self._on_motion, add='+')
        self.bind('<Leave>', self._on_leave, add='+')
        self.bind('<Button-1>', self._on_press, add='+')
        self.bind('<B1-Motion>', self._on_drag, add='+')
        self.bind('<ButtonRelease-1>', self._on_release, add='+')
        self._draw()

    @property
    def dragging(self):
        return bool(self._dragging)

    def set(self, first, last):
        try:
            first_f = max(0.0, min(1.0, float(first)))
            last_f = max(first_f, min(1.0, float(last)))
        except Exception:
            return
        self._first, self._last = first_f, last_f
        self._draw()

    def _on_configure(self, _event=None):
        self._draw()

    def _viewport_fraction(self):
        return max(0.0, min(1.0, self._last - self._first))

    def _geometry(self):
        try:
            w = max(6, int(self.winfo_width()))
            h = max(8, int(self.winfo_height()))
        except Exception:
            w, h = 12, 100
        pad_x = 2
        pad_y = 3
        track_h = max(1, h - 2 * pad_y)
        visible = self._viewport_fraction()
        if visible >= 0.999:
            thumb_h = track_h
            top = pad_y
        else:
            thumb_h = max(self._min_thumb_px, int(round(track_h * visible)))
            thumb_h = min(track_h, thumb_h)
            travel = max(0, track_h - thumb_h)
            max_first = max(1e-9, 1.0 - visible)
            ratio = max(0.0, min(1.0, self._first / max_first))
            top = pad_y + int(round(travel * ratio))
        bottom = min(h - pad_y, top + thumb_h)
        return (pad_x, pad_y, w - pad_x, h - pad_y, top, bottom)

    def _draw(self):
        try:
            x0, y0, x1, y1, top, bottom = self._geometry()
            self.delete('all')
            # Track discreto. El thumb es la única pieza que cambia de color.
            self.create_rectangle(x0, y0, x1, y1, fill=self._track_color, outline='')
            color = self._thumb_hover_color if (self._hover or self._dragging) else self._thumb_color
            self.create_rectangle(x0, top, x1, bottom, fill=color, outline='')
            self._thumb_bounds = (x0, top, x1, bottom)
        except Exception:
            pass

    def _is_over_thumb(self, x, y):
        x0, y0, x1, y1 = self._thumb_bounds
        return x0 <= x <= x1 and y0 <= y <= y1

    def _on_motion(self, event):
        hover = self._is_over_thumb(float(event.x), float(event.y))
        if hover != self._hover:
            self._hover = hover
            self._draw()
        try:
            self.configure(cursor='sb_v_double_arrow' if hover else 'arrow')
        except Exception:
            pass

    def _on_leave(self, _event=None):
        if not self._dragging and self._hover:
            self._hover = False
            self._draw()

    def _fraction_from_thumb_top(self, thumb_top):
        try:
            _x0, pad_y, _x1, track_bottom, top, bottom = self._geometry()
            track_h = max(1.0, float(track_bottom - pad_y))
            thumb_h = max(1.0, float(bottom - top))
            travel = max(0.0, track_h - thumb_h)
            visible = self._viewport_fraction()
            max_first = max(0.0, 1.0 - visible)
            if travel <= 0.0 or max_first <= 0.0:
                return 0.0
            local = max(0.0, min(travel, float(thumb_top) - float(pad_y)))
            return (local / travel) * max_first
        except Exception:
            return self._first

    def _on_press(self, event):
        try:
            x, y = float(event.x), float(event.y)
        except Exception:
            return 'break'
        _x0, top, _x1, bottom = self._thumb_bounds
        over_thumb = self._is_over_thumb(x, y)
        if over_thumb:
            self._drag_grip_y = y - top
        else:
            self._drag_grip_y = max(0.0, (bottom - top) / 2.0)
        self._dragging = True
        self._hover = True
        self._draw()
        try:
            self.grab_set()
        except Exception:
            pass
        if callable(self._on_drag_start):
            try:
                self._on_drag_start()
            except Exception:
                pass
        if not over_thumb:
            target = self._fraction_from_thumb_top(y - self._drag_grip_y)
            self._request_fraction(target, immediate=True)
        return 'break'

    def _on_drag(self, event):
        if not self._dragging:
            return 'break'
        try:
            target = self._fraction_from_thumb_top(float(event.y) - self._drag_grip_y)
        except Exception:
            return 'break'
        self._request_fraction(target, immediate=False)
        return 'break'

    def _request_fraction(self, fraction, *, immediate=False):
        self._pending_fraction = max(0.0, min(1.0, float(fraction)))
        if immediate:
            self._flush_drag_frame(force=True)
            return
        if self._drag_after is not None:
            return
        elapsed_ms = (time.monotonic() - self._last_drag_frame) * 1000.0
        delay = 0 if elapsed_ms >= self._frame_ms else max(0, int(self._frame_ms - elapsed_ms))
        try:
            self._drag_after = self.after(delay, self._flush_drag_frame)
        except Exception:
            self._drag_after = None

    def _flush_drag_frame(self, force=False):
        if self._drag_after is not None:
            try:
                self.after_cancel(self._drag_after)
            except Exception:
                pass
            self._drag_after = None
        fraction = self._pending_fraction
        self._pending_fraction = None
        if fraction is None:
            return
        self._last_drag_frame = time.monotonic()
        try:
            self._command('moveto', fraction)
        except Exception:
            return
        # Si llegaron más movimientos durante el commit, conservamos sólo el
        # más reciente para el próximo frame.
        if self._pending_fraction is not None and not force:
            self._request_fraction(self._pending_fraction, immediate=False)

    def _on_release(self, _event=None):
        if not self._dragging:
            return 'break'
        self._flush_drag_frame(force=True)
        self._dragging = False
        self._hover = False
        try:
            self.grab_release()
        except Exception:
            pass
        self._draw()
        if callable(self._on_drag_end):
            try:
                self._on_drag_end()
            except Exception:
                pass
        return 'break'

    def destroy(self):
        if self._drag_after is not None:
            try:
                self.after_cancel(self._drag_after)
            except Exception:
                pass
            self._drag_after = None
        super().destroy()


class StableScrollHost(ctk.CTkFrame):
    """Viewport nativo y compatible con las páginas existentes de CorePulse."""

    def __init__(
        self,
        master,
        *,
        fg_color=DEFAULT_BG,
        scrollbar_button_color=DEFAULT_SCROLLBAR,
        scrollbar_button_hover_color=DEFAULT_SCROLLBAR_HOVER,
        scroll_hold_ms=220,
        wheel_pixels=96,
        motion_frame_ms=None,
        backend='canvas',
        **kwargs,
    ):
        kwargs.setdefault('corner_radius', 0)
        kwargs.setdefault('border_width', 0)
        super().__init__(master, fg_color=fg_color, **kwargs)

        self._bg = fg_color if isinstance(fg_color, str) and fg_color != 'transparent' else DEFAULT_BG
        self._backend = 'place' if str(backend).strip().lower() == 'place' else 'canvas'
        self._place_offset_y = 0.0
        self._content_height_px = 1
        self._scroll_hold = max(0.12, float(scroll_hold_ms) / 1000.0)
        self._wheel_pixels = max(18.0, float(wheel_pixels))
        policy = get_ui_refresh_policy()
        self._repaint_frame_ms = max(8, int(motion_frame_ms or policy.frame_ms))
        self._scroll_active_until = 0.0
        self._destroyed = False
        self._drag_active = False
        self._geometry_dirty = False

        self._geometry_after = None
        self._resize_geometry_after = None
        self._pending_canvas_width = None
        self._idle_after = None
        self._repaint_after = None
        self._repaint_strong_pending = False
        self._idle_callbacks = []
        self._last_repaint_ts = 0.0
        self._scrollbar_visible = True

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Backend por defecto: Canvas nativo. Para páginas CTk muy densas en
        # Windows existe el backend ``place``: el contenido vive dentro de un
        # viewport normal y se desplaza moviendo UN único frame hijo. Así se
        # evita el desfase de pintura entre Canvas.create_window y los HWND de
        # los widgets CTk observado en los resultados del Benchmark.
        if self._backend == 'place':
            self.viewport = tk.Frame(
                self, bg=self._bg, bd=0, highlightthickness=0, relief='flat', takefocus=0
            )
            self.viewport.grid(row=0, column=0, sticky='nsew')
            # ``canvas`` se mantiene como alias de compatibilidad para código
            # que sólo necesita winfo/update_idletasks. No expone yview.
            self.canvas = self.viewport
        else:
            self.viewport = tk.Canvas(
                self,
                bg=self._bg,
                bd=0,
                highlightthickness=0,
                relief='flat',
                takefocus=0,
                yscrollincrement=1,
            )
            self.viewport.grid(row=0, column=0, sticky='nsew')
            self.canvas = self.viewport

        self.scrollbar = _CorePulseDragScrollbar(
            self,
            command=self._scrollbar_command,
            on_drag_start=self._on_scrollbar_drag_start,
            on_drag_end=self._on_scrollbar_drag_end,
            frame_ms=self._repaint_frame_ms,
            bg=self._bg,
            track_color=DEFAULT_SCROLLBAR_TRACK,
            thumb_color=scrollbar_button_color,
            thumb_hover_color=scrollbar_button_hover_color,
            width=12,
        )
        self.scrollbar.grid(row=0, column=1, sticky='ns', padx=(4, 0))
        # Compatibilidad con helpers históricos del Dashboard que consultan
        # ``_scrollbar`` directamente.
        self._scrollbar = self.scrollbar

        self.content = ctk.CTkFrame(self.viewport, fg_color=self._bg, corner_radius=0, border_width=0)
        if self._backend == 'place':
            self._window_item = None
            self.content.place(x=0, y=0, relwidth=1.0)
        else:
            self._window_item = self.canvas.create_window((0, 0), window=self.content, anchor='nw')
            self.canvas.configure(yscrollcommand=self._on_canvas_yview)

        self.content.bind('<Configure>', self._on_content_configure, add='+')
        self.viewport.bind('<Configure>', self._on_canvas_configure, add='+')
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
        return bool(self._drag_active or time.monotonic() < self._scroll_active_until)

    def _on_wheel(self, event):
        if self._destroyed:
            return None
        try:
            first, last = self.yview()
            if last - first >= 0.999:
                return None
        except Exception:
            return None

        delta = float(getattr(event, 'delta', 0) or 0)
        num = getattr(event, 'num', None)
        if num == 4:
            px = -self._wheel_pixels * 1.25
        elif num == 5:
            px = self._wheel_pixels * 1.25
        elif delta:
            px = (-delta / 120.0) * self._wheel_pixels
            if 0.0 < abs(px) < 1.0:
                px = -1.0 if px < 0 else 1.0
        else:
            return None

        self._mark_scrolling()
        self._scroll_by_pixels(px)
        return 'break'

    def _scroll_by_pixels(self, pixels):
        try:
            amount = int(round(float(pixels)))
            if amount == 0:
                return
            if self._backend == 'place':
                self._place_scroll_pixels(amount)
            else:
                self.canvas.yview_scroll(amount, 'units')
            self._after_direct_scroll(immediate=False)
        except Exception:
            pass

    def _on_scrollbar_drag_start(self):
        if self._destroyed:
            return
        self._drag_active = True
        self._geometry_dirty = False
        self._mark_scrolling(0.60)
        # No permitir que un Configure atrasado cambie scrollregion a mitad del
        # gesto: es una de las fuentes de saltos y restos visuales.
        if self._geometry_after is not None:
            try:
                self.after_cancel(self._geometry_after)
            except Exception:
                pass
            self._geometry_after = None

    def _on_scrollbar_drag_end(self):
        if self._destroyed:
            return
        self._drag_active = False
        self._mark_scrolling(0.10)
        # Último frame fuerte: borrar restos del punto anterior antes de volver
        # a permitir renders/Configure diferidos.
        self._flush_repaint(strong=True)
        if self._geometry_dirty:
            self._geometry_dirty = False
            self._schedule_geometry(0)
        self._schedule_idle_flush()

    def _scrollbar_command(self, *args):
        if not args or self._destroyed:
            return
        self._mark_scrolling(0.35 if self._drag_active else 0.20)
        try:
            op = str(args[0])
            if op == 'moveto' and len(args) >= 2:
                fraction = max(0.0, min(1.0, float(args[1])))
                if self._backend == 'place':
                    self._place_moveto(fraction)
                else:
                    self.canvas.yview_moveto(fraction)
            elif op == 'scroll' and len(args) >= 3:
                amount = int(float(args[1]))
                unit = str(args[2])
                if self._backend == 'place':
                    if unit == 'pages':
                        page = max(1, int(self.viewport.winfo_height()))
                        self._place_scroll_pixels(amount * page)
                    else:
                        self._place_scroll_pixels(amount * int(round(self._wheel_pixels)))
                elif unit == 'pages':
                    self.canvas.yview_scroll(amount, 'pages')
                else:
                    self.canvas.yview_scroll(amount * int(round(self._wheel_pixels)), 'units')
            else:
                fraction = max(0.0, min(1.0, float(args[-1])))
                if self._backend == 'place':
                    self._place_moveto(fraction)
                else:
                    self.canvas.yview_moveto(fraction)
            # El thumb propio ya limita los eventos de drag a 8-16 ms. En ese
            # frame hacemos repaint fuerte e inmediato: no queda una cola de
            # posiciones antiguas acumulándose detrás del puntero.
            self._after_direct_scroll(immediate=self._drag_active)
        except Exception:
            return

    @property
    def backend(self):
        return self._backend

    def _place_metrics(self):
        try:
            viewport_h = max(1, int(self.viewport.winfo_height()))
        except Exception:
            viewport_h = 1
        total_h = max(viewport_h, int(self._content_height_px or 1))
        max_offset = max(0.0, float(total_h - viewport_h))
        return viewport_h, total_h, max_offset

    def _place_commit_offset(self, offset):
        _vh, total_h, max_offset = self._place_metrics()
        self._place_offset_y = max(0.0, min(max_offset, float(offset)))
        try:
            self.content.place_configure(y=-int(round(self._place_offset_y)))
        except Exception:
            pass
        first = (self._place_offset_y / float(total_h)) if total_h > 0 else 0.0
        last = ((self._place_offset_y + _vh) / float(total_h)) if total_h > 0 else 1.0
        self._on_canvas_yview(max(0.0, min(1.0, first)), max(0.0, min(1.0, last)))

    def _place_moveto(self, fraction):
        _vh, total_h, _max_offset = self._place_metrics()
        self._place_commit_offset(max(0.0, min(1.0, float(fraction))) * float(total_h))

    def _place_scroll_pixels(self, pixels):
        self._place_commit_offset(self._place_offset_y + float(pixels))

    def _after_direct_scroll(self, *, immediate=False):
        # V185: en Windows también la rueda del mouse necesita invalidación con
        # borrado. El repaint suave podía dejar durante unas décimas una copia
        # del frame anterior (texto fantasma) aunque el árbol de widgets fuese
        # correcto. Se conserva el throttle por frame para no repintar de más.
        if immediate:
            self._flush_repaint(strong=True)
        else:
            self._schedule_repaint(strong=(sys.platform == 'win32'))

    def _schedule_repaint(self, *, strong=False):
        self._repaint_strong_pending = bool(self._repaint_strong_pending or strong)
        if self._destroyed or self._repaint_after is not None:
            return
        now = time.monotonic()
        elapsed_ms = (now - self._last_repaint_ts) * 1000.0
        delay = 0 if elapsed_ms >= self._repaint_frame_ms else max(0, int(self._repaint_frame_ms - elapsed_ms))
        try:
            self._repaint_after = self.after(delay, self._flush_repaint)
        except Exception:
            self._repaint_after = None

    def _windows_repaint(self, *, strong=False):
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # Normal: invalidate + all children + update now.
            # Drag: ERASE + ERASENOW borra el frame viejo antes de pintar el
            # nuevo; esto es lo que evita el texto duplicado observado.
            flags = 0x0001 | 0x0080 | 0x0100  # INVALIDATE | ALLCHILDREN | UPDATENOW
            if strong:
                flags |= 0x0004 | 0x0200       # ERASE | ERASENOW
            targets = [self]
            if strong:
                targets.extend((self.canvas, self.content))
            seen = set()
            for widget in targets:
                try:
                    hwnd = int(widget.winfo_id())
                    if hwnd in seen:
                        continue
                    seen.add(hwnd)
                    user32.RedrawWindow(hwnd, 0, 0, flags)
                    user32.UpdateWindow(hwnd)
                except Exception:
                    pass
            if strong:
                try:
                    ctypes.windll.gdi32.GdiFlush()
                except Exception:
                    pass
        except Exception:
            pass

    def _flush_repaint(self, strong=False):
        strong = bool(strong or self._repaint_strong_pending)
        self._repaint_strong_pending = False
        if self._repaint_after is not None:
            try:
                self.after_cancel(self._repaint_after)
            except Exception:
                pass
            self._repaint_after = None
        if self._destroyed:
            return
        try:
            # update_idletasks procesa geometría/expose sin entrar en un update()
            # reentrante que podría ejecutar callbacks de telemetría durante drag.
            self.canvas.update_idletasks()
            self.content.update_idletasks()
            self.update_idletasks()
        except Exception:
            pass
        self._windows_repaint(strong=bool(strong))
        self._last_repaint_ts = time.monotonic()

    def _on_canvas_yview(self, first, last):
        try:
            first_f, last_f = float(first), float(last)
            self.scrollbar.set(first_f, last_f)
            needs = (last_f - first_f) < 0.999
            if needs and not self._scrollbar_visible:
                self.scrollbar.grid()
                self._scrollbar_visible = True
            elif not needs and self._scrollbar_visible:
                self.scrollbar.grid_remove()
                self._scrollbar_visible = False
        except Exception:
            pass

    def _window_is_resizing(self):
        """Consulta la autoridad de resize del Toplevel sin acoplarse al App."""
        try:
            top = self.winfo_toplevel()
            return bool(getattr(top, 'is_resizing', False))
        except Exception:
            return False

    def _schedule_post_resize_geometry(self):
        if self._destroyed or self._resize_geometry_after is not None:
            return
        try:
            self._resize_geometry_after = self.after(110, self._flush_post_resize_geometry)
        except Exception:
            self._resize_geometry_after = None

    def _flush_post_resize_geometry(self):
        self._resize_geometry_after = None
        if self._destroyed:
            return
        if self._window_is_resizing():
            self._schedule_post_resize_geometry()
            return
        try:
            if self._pending_canvas_width is not None and self._backend == 'canvas':
                self.canvas.itemconfigure(self._window_item, width=max(1, int(self._pending_canvas_width)))
        except Exception:
            pass
        self._pending_canvas_width = None
        self._geometry_dirty = False
        self._refresh_geometry()

    def _on_canvas_configure(self, event=None):
        try:
            width = max(1, int(getattr(event, 'width', self.canvas.winfo_width())))
        except Exception:
            width = None
        if self._window_is_resizing():
            # V148: cambiar el ancho de la ventana Canvas fuerza a CTk a
            # recalcular cada tarjeta hija. Durante el drag guardamos sólo el
            # último ancho y lo publicamos al finalizar el gesto.
            self._pending_canvas_width = width
            self._geometry_dirty = True
            self._schedule_post_resize_geometry()
            return
        try:
            if width is not None and self._backend == 'canvas':
                self.canvas.itemconfigure(self._window_item, width=width)
        except Exception:
            pass
        self._schedule_geometry(8)

    def _on_content_configure(self, _event=None):
        if self._window_is_resizing():
            self._geometry_dirty = True
            self._schedule_post_resize_geometry()
            return
        self._schedule_geometry(8)

    def _schedule_scrollregion(self, delay_ms=12):
        self._schedule_geometry(delay_ms)

    def _refresh_scrollregion(self):
        self._refresh_geometry()

    def _schedule_geometry(self, delay_ms=12):
        if self._destroyed:
            return
        if self._drag_active:
            self._geometry_dirty = True
            return
        if self._window_is_resizing():
            self._geometry_dirty = True
            self._schedule_post_resize_geometry()
            return
        if self._geometry_after is not None:
            try:
                self.after_cancel(self._geometry_after)
            except Exception:
                pass
        try:
            self._geometry_after = self.after(max(0, int(delay_ms)), self._refresh_geometry)
        except Exception:
            self._geometry_after = None

    def _refresh_geometry(self):
        self._geometry_after = None
        if self._destroyed:
            return
        if self._drag_active:
            self._geometry_dirty = True
            return
        try:
            width = max(1, int(self.viewport.winfo_width()))
            if self._backend == 'place':
                # No Canvas.create_window: todos los widgets CTk quedan bajo un
                # frame normal y Windows los recorta con el viewport. El alto
                # real se obtiene después de resolver geometría del árbol.
                self.content.update_idletasks()
                self._content_height_px = max(1, int(self.content.winfo_reqheight()))
                self.content.place_configure(x=0, relwidth=1.0)
                self._place_commit_offset(self._place_offset_y)
            else:
                self.canvas.itemconfigure(self._window_item, width=width)
                req_h = max(1, int(self.content.winfo_reqheight()))
                self.canvas.configure(scrollregion=(0, 0, width, req_h))
                first, last = self.canvas.yview()
                self._on_canvas_yview(first, last)
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
            self._idle_after = self.after(48, self._flush_idle_callbacks)
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
        try:
            if self._backend == 'place':
                vh, total_h, _max_offset = self._place_metrics()
                first = self._place_offset_y / float(total_h) if total_h > 0 else 0.0
                last = (self._place_offset_y + vh) / float(total_h) if total_h > 0 else 1.0
                return (max(0.0, min(1.0, first)), max(0.0, min(1.0, last)))
            return tuple(float(v) for v in self.canvas.yview())
        except Exception:
            return (0.0, 1.0)

    def yview_moveto(self, fraction):
        try:
            self._mark_scrolling(0.16)
            fraction = max(0.0, min(1.0, float(fraction)))
            if self._backend == 'place':
                self._place_moveto(fraction)
            else:
                self.canvas.yview_moveto(fraction)
            self._after_direct_scroll(immediate=False)
        except Exception:
            pass

    def destroy(self):
        self._destroyed = True
        if self._router is not None:
            try:
                self._router.unregister(self)
            except Exception:
                pass
        for after_id in (self._geometry_after, self._resize_geometry_after, self._idle_after, self._repaint_after):
            if after_id is not None:
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
        self._idle_callbacks.clear()
        super().destroy()
