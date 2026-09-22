# CorePulse V193 — Benchmark GPU V16 · Clarity Finish

Objetivo: cerrar la legibilidad y la transición de resultados sin alterar el benchmark medido.

## Cambios
- Sin hueco intencional entre progreso y dashboard: el dashboard se construye primero y luego se publica.
- GPU 3D prioriza FPS y 1% Low. Frametime, CV, spikes y tiempos internos quedan bajo `Ver detalles técnicos`.
- Sistema prioriza SHA-256, RAM Copia y SSD Lectura/Escritura.
- Evidencia muestra un resumen de trazabilidad antes de la metodología completa.
- Bordes de tarjetas reforzados con `BENCH_BORDER`.
- Historial no retira su loading card hasta que la vista construida está lista.

## Integridad
No se modifican `core/directx_scene.py`, `core/directx_benchmark.py` ni `core/benchmark_engine.py`. La metodología sigue siendo GPU V16.
