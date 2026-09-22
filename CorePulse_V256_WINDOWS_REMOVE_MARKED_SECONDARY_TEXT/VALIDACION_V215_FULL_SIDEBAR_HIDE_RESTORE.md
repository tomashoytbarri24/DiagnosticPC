# V215 — Windows Mainline · Full Sidebar Hide / Restore

## Objetivo
Corregir el comportamiento del botón lateral: al ocultar, debe desaparecer **todo el sidebar**, no quedar un rail con iconos.

## Cambios aplicados
- Al colapsar se ejecuta `sidebar.grid_remove()`: el panel lateral completo sale del layout.
- La columna izquierda deja de reservar ancho y el dashboard ocupa ese espacio inmediatamente.
- El botón flotante permanece visible en el borde izquierdo para restaurar el sidebar.
- Al expandir, el sidebar se reconstruye y vuelve a `grid(row=0, column=0, sticky='nsew')`.
- El efecto motion blur se conserva como una estela visual entre la posición anterior y la nueva, sin animar el ancho real del dashboard.

## Política
- No se toca la telemetría ni REAL_OR_NA.
- El cambio es exclusivamente de navegación/layout visual.
