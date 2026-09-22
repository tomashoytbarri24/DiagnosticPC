# Validación V185 — Benchmark V16 UI Ghost Fix

Objetivo: eliminar restos de píxeles/texto del frame anterior durante scroll en Windows sin cambiar el benchmark GPU V16.

Criterios:
- `core/directx_benchmark.py`, `core/directx_scene.py` y `core/benchmark_engine.py` conservan SHA-256 de V184.
- La rueda del mouse solicita repaint fuerte en Windows, limitado por el frame scheduler.
- Una petición fuerte no se pierde si ya existe un repaint programado.
- No se introduce `update()` reentrante.
- Benchmark sigue persistiendo `benchmark_gpu_v16_ultimo_resultado.json`.

## Resultado estático
- `py_compile`: PASS.
- Suite vigente V179/V180/V184/V185 + motor de scroll: **21/21 PASS** (1 guard V184 de versión literal deseleccionado).
- Los guards V181 que exigen hashes del antiguo Benchmark V13 no aplican a V16 y no se usan como criterio de V185.
- SHA-256 de `core/directx_benchmark.py`, `core/directx_scene.py` y `core/benchmark_engine.py`: idénticos a V184.
