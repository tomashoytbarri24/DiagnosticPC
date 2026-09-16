"""Agrupa redibujos de tamaño CTk por ventana mientras se redimensiona.

V159 conserva el manejador original de CustomTkinter, incluidas sus conversiones
de DPI y posibles extensiones. Sólo aplaza sus llamadas a _draw durante el gesto;
los cambios de color/contenido fuera de ese manejador siguen dibujando normalmente.
La aplicación pasa owner=app para no congelar diálogos ni otras ventanas.
Todas las funciones se invocan desde el hilo de Tk.
"""
from __future__ import annotations

import logging
import weakref

logger = logging.getLogger('CorePulse.Resize')
_installed = False
_active = False  # Compatibilidad con consumidores de set_active(active) de V158.
_owners = weakref.WeakSet()
_dirty = weakref.WeakKeyDictionary()
_original_update_dimensions_event = None
_MISSING = object()


def _resolve_base_class():
    try:
        from customtkinter.windows.widgets.core_widget_classes.ctk_base_class import CTkBaseClass
        return CTkBaseClass
    except ImportError:
        return None


def _window(widget):
    try:
        return widget.winfo_toplevel()
    except Exception:
        return None


def _patched_update_dimensions_event(self, event):
    owner = _window(self) if _owners else None
    if not _active and owner not in _owners:
        return _original_update_dimensions_event(self, event)

    # Dejar al proveedor actualizar dimensiones y ejecutar sus propios efectos.
    # La sustitución dura únicamente esta llamada síncrona y se restaura incluso
    # si el manejador lanza una excepción. No se enlazan callbacks nuevos por píxel.
    previous = vars(self).get('_draw', _MISSING)

    def defer_draw(*args, **kwargs):
        root = owner if owner is not None else _window(self)
        old = _dirty.get(self)
        if old and old[1].get('no_color_updates') is False:
            kwargs['no_color_updates'] = False
        _dirty[self] = (args, dict(kwargs), weakref.ref(root) if root is not None else None)

    self._draw = defer_draw
    try:
        return _original_update_dimensions_event(self, event)
    finally:
        if previous is _MISSING:
            del self._draw
        else:
            self._draw = previous


def install():
    """Instala una sola envoltura antes de crear widgets, conservando el original."""
    global _installed, _original_update_dimensions_event
    if _installed:
        return True
    base_cls = _resolve_base_class()
    if base_cls is None:
        return False
    original = getattr(base_cls, '_corepulse_resize_guard_original', None)
    if original is None:
        original = getattr(base_cls, '_update_dimensions_event', None)
    if not callable(original):
        return False
    _original_update_dimensions_event = original
    base_cls._corepulse_resize_guard_original = original
    base_cls._update_dimensions_event = _patched_update_dimensions_event
    base_cls._corepulse_resize_guard_installed = True
    _installed = True
    return True


def set_active(active, *, owner=None):
    """Agrupa por toplevel; desactivar una ventana no libera ni congela otra."""
    global _active
    if owner is None:
        _active = bool(active)
    elif active:
        _owners.add(owner)
    else:
        _owners.discard(owner)
    if not active:
        flush(owner=owner)


def flush(*, owner=None):
    """Dibuja el último tamaño de cada widget pendiente una vez, si aún existe."""
    for widget, (args, kwargs, root_ref) in list(_dirty.items()):
        if owner is not None and (root_ref is None or root_ref() is not owner):
            continue
        # Eliminar antes de dibujar: un evento anidado podrá volver a encolarlo.
        _dirty.pop(widget, None)
        try:
            if widget.winfo_exists():
                widget._draw(*args, **kwargs)
        except Exception:
            logger.debug('No se pudo redibujar un widget pendiente', exc_info=True)


def release(owner):
    """Retira la ventana al cerrarla, sin redibujar widgets en destrucción."""
    _owners.discard(owner)
    for widget, (_, _, root_ref) in list(_dirty.items()):
        if root_ref is not None and root_ref() is owner:
            _dirty.pop(widget, None)


def is_active(owner=None):
    return bool(_active or (owner in _owners if owner is not None else _owners))


def is_installed():
    return _installed


def pending_count():
    return len(_dirty)
