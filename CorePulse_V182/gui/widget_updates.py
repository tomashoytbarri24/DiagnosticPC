"""Escrituras visuales sólo cuando cambia el valor real del widget.

Se consulta cget en lugar de cachear: otros módulos y el tema pueden modificar
el mismo control. Sin monkeypatches ni referencias globales a widgets destruidos.
"""


def configure_changed(widget, **values):
    if widget is None:
        return False
    changed = {}
    for key, value in values.items():
        try:
            current = widget.cget(key)
            if isinstance(current, (list, tuple)) and isinstance(value, (list, tuple)):
                equal = tuple(current) == tuple(value)
            else:
                equal = current == value
            if equal:
                continue
        except Exception:
            # Opciones no consultables mantienen su comportamiento original.
            pass
        changed[key] = value
    if not changed:
        return False
    widget.configure(**changed)
    return True


def set_changed(widget, value):
    try:
        if widget.get() == value:
            return False
    except Exception:
        pass
    widget.set(value)
    return True
