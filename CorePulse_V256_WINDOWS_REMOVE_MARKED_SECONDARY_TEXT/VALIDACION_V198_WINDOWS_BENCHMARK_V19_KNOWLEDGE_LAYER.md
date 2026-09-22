# VALIDACIÓN V198 — Windows · Benchmark GPU V19 · Knowledge Layer

## Alcance
V198 conserva el workload GPU V19 y añade interpretación determinista de resultados.

## Workload preservado
- `core/directx_scene.py`: SHA-256 `21716b2013cfcee87330f81620a71791952024474af2e734c30d4c7fa6f32e2b`
- `core/directx_benchmark.py`: SHA-256 `754b46a53e379db6bb4cec1b109a4231b86f391395067a0efa28ac6495f68cd7`
- `core/benchmark_engine.py`: SHA-256 `255be8fc4267944472a060e8fd793bc5cbb2471cd3d692911a5bb3d9d0e56891`

Coinciden byte por byte con V197. Benchmark GPU sigue siendo **V19** y persiste en `resultados/benchmark_gpu_v19_ultimo_resultado.json`.

## Knowledge Layer
- CPU: estado + integridad + calidad de muestras + temperatura real.
- RAM: integridad byte a byte + estabilidad de muestras.
- SSD: E/S real + estabilidad; diferencia explícita entre rendimiento y SMART/desgaste.
- GPU: escenas completadas + FPS/1% Low + temperatura; 1% Low expresado también como porcentaje del promedio.
- Evidencia térmica: explica warning, margen a TjMax y racha de safety con muestras observadas.

## Pruebas
- `tests/test_v198_benchmark_v19_knowledge_layer.py`: 7/7 PASS.
- Regresión funcional seleccionada V197/safety/live health: 22 PASS, 2 guards históricos deseleccionados (`VERSION==197` y hashes V13).
- `python -m compileall -q core gui tools`: PASS.

## Limitación de entorno
El render visible DirectX y el layout físico 1280×800 deben confirmarse en Windows real. V198 no cambia el workload, por lo que el foco de la prueba visual es la nueva capa explicativa y su densidad.
