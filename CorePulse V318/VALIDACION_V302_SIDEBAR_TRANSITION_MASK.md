# VALIDACIÓN V302 — SIDEBAR TRANSITION MASK

## Base
- V301.

## Objetivo
Reducir el ruido visual observado al ocultar/mostrar el sidebar, especialmente los frames parciales de tarjetas y gráficos durante el reflow horizontal.

## Implementación
- Máscara reutilizable sobre `main_content` antes de cambiar el grid.
- `layout_transition` pausa el reflow de gráficos mientras cambia la geometría.
- Matplotlib se sincroniza y dibuja una sola vez bajo la máscara.
- El contenido se revela con un wipe breve de izquierda a derecha.
- El sidebar no se reconstruye.
- Telemetría y datos permanecen intactos.
