# VALIDACIÓN V308 — SIDEBAR FAST ATOMIC

## Base
- V306, por ser la última transición visual estable.
- Se descarta el movimiento real del sidebar introducido en V307.

## Corrección
- El sidebar no usa `place()` durante el gesto.
- `WM_SETREDRAW` mantiene ocultos los estados intermedios.
- El layout usa fast-path (`force=False`).
- Matplotlib ya no ejecuta `canvas.draw()` de forma síncrona durante el clic.
- El redraw de charts se programa con `draw_idle` después del frame final.

## Resultado esperado
- Reacción más rápida que V306.
- Sin cuadros deformados ni sidebar desarmándose como en V307.
