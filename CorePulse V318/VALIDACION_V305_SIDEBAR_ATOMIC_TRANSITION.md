# VALIDACIÓN V305 — SIDEBAR ATOMIC TRANSITION

## Problema observado
En el video de V304, al abrir el sidebar los hijos se dibujaban por etapas: primero fondo/selección y luego iconos, separadores y textos; al mismo tiempo las cards y Matplotlib atravesaban geometrías intermedias.

## Solución
- Captura temporal del frame real ya visible con Pillow ImageGrab.
- Reflow de Tk/CustomTkinter y Matplotlib oculto detrás de esa captura.
- Publicación del estado final en un único cambio visual.
- Sin velo oscuro, wipe, estela ni animación progresiva de widgets.

## Fallback
Si la captura no está disponible, se conserva el settle agrupado sin depender de ella.
