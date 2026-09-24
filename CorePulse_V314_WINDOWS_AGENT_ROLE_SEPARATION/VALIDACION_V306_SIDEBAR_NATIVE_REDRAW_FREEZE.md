# VALIDACIÓN V306 — SIDEBAR NATIVE REDRAW FREEZE

## Base
- Proyecto base: V305.

## Problema observado
- Tk/CustomTkinter mostraba durante unos frames el reflow de tarjetas, separadores y Matplotlib al cambiar el ancho disponible.
- Las soluciones con máscara, wipe, velo o snapshot seguían siendo visualmente invasivas.

## Solución V306
- No hay animación ni overlay.
- Windows recibe WM_SETREDRAW=FALSE antes del cambio de grid.
- Tk, CTk y Matplotlib estabilizan la geometría mientras la ventana no publica frames intermedios.
- Luego se reactiva WM_SETREDRAW y se fuerza un único RedrawWindow final con todos los hijos.

## Integridad
- No cambia telemetría, sensores, REAL_OR_NA ni REAL_FPS_OR_NA_ONLY.
