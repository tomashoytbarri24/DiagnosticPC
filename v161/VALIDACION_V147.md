# Validación V147 — Diagnóstico responsive y scroll estable

## Objetivo
Evitar que el informe final del Diagnóstico Completo quede cortado en modo ventana, 1280×720/800, maximizado u otras dimensiones.

## Cambios
- `gui.diagnostic_view` usa `StableScrollHost` para el área de evidencia/resultado.
- Rueda configurada en 96 px por notch para navegación inmediata.
- Breakpoints de ancho ajustan proporción del gauge y el área del informe.
- Breakpoint estrecho convierte las seis tarjetas a una columna.
- Tarjetas y prioridad usan padding vertical reducido.
- Evidencia de portada se limita visualmente sin alterar la evidencia real almacenada.

## Política
- No cambia REAL_OR_NA.
- No cambia el motor de diagnóstico, estrés o benchmark.
- No cambia SMART/NVMe ni runtime.
- No se eliminan componentes ni acciones del resultado.
