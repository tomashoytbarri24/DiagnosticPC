# Validación V148 — Resize fluido y diagnóstico adaptativo

## Objetivo
Eliminar el lag al arrastrar los bordes de CorePulse, especialmente con el resultado del Diagnóstico Completo visible, sin sacrificar la adaptación a distintas dimensiones.

## Cambios
- La autoridad global de resize usa un único temporizador trailing en vez de cancelar/recrear callbacks por cada píxel.
- `DiagnosticExperiencePanel` sólo recompone grids al cruzar breakpoints o al terminar el gesto de resize.
- `DiagnosticGauge` difiere repaints de `<Configure>`.
- `StableScrollHost` conserva el último ancho y aplaza scrollregion/reflow hasta que termina el resize.
- El resultado del diagnóstico usa 3 columnas en viewport amplio, 2 en medio y 1 en estrecho.
- En modo ventana el gauge cede más ancho al informe.

## Política
- No cambia REAL_OR_NA.
- No cambia estrés, benchmark, SMART/NVMe ni runtime.
- No se ocultan tarjetas ni acciones.
