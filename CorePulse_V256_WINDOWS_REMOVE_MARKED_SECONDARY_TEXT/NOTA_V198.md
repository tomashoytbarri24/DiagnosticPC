# CorePulse V198 — Knowledge Layer

Base: V197 Windows Mainline. Benchmark GPU: **V19 sin cambios**.

## Objetivo
CorePulse no debe limitarse a mostrar números. V198 añade una lectura humana y trazable para que el usuario entienda si cada prueba terminó correctamente, qué merece atención y qué NO puede inferirse de ese benchmark.

## Regla de interpretación
- Nunca usa rankings externos ni puntuaciones inventadas.
- `FUNCIONA CORRECTAMENTE EN ESTA PRUEBA` significa que **esa prueba** terminó con evidencia válida; no afirma que todo el componente esté sano en cualquier condición.
- CPU: usa estado, integridad, `measurement_quality` y temperatura real.
- RAM: requiere verificación real de integridad para afirmar que la copia fue correcta.
- SSD: interpreta E/S; SMART sigue siendo necesario para salud física/desgaste.
- GPU: usa finalización de escenas, FPS/1% Low, timestamps/telemetría disponibles y temperatura. El 1% Low se explica como porcentaje del promedio, no como ranking de mercado.
- Safety: la evidencia térmica explica muestras reales y rachas; no interpola sensores.

## Integridad V19
`directx_scene.py`, `directx_benchmark.py` y `benchmark_engine.py` son byte-identical a V197.
