# Validación V197 — Windows / Benchmark GPU V19 UX Closure

Base directa: V196 Windows Mainline.

## Alcance

V197 es una iteración exclusivamente de UX/presentación. No modifica el workload medido del Benchmark GPU V19.

Cambios:
- Historial: 3 ejecuciones visibles inicialmente, 5 sesiones en la primera precarga y resto en segundo plano.
- Terminología técnica más legible: `Frame presentado`, `Variación`, `Frames lentos`, `Compresión zlib`, `Descompresión zlib` y `Variación (CV)`.
- Resumen térmico: acceso directo a Evidencia cuando existe temperatura alta o safety stop.
- Evidencia térmica: el conteo se expresa como `Muestras sobre X °C`.

## Integridad del benchmark V19

Los tres archivos que determinan el workload/medición permanecen byte a byte iguales a V196:

- `core/directx_scene.py` — `21716b2013cfcee87330f81620a71791952024474af2e734c30d4c7fa6f32e2b`
- `core/directx_benchmark.py` — `754b46a53e379db6bb4cec1b109a4231b86f391395067a0efa28ac6495f68cd7`
- `core/benchmark_engine.py` — `255be8fc4267944472a060e8fd793bc5cbb2471cd3d692911a5bb3d9d0e56891`

Se conserva:
- Benchmark GPU V19.
- Direct3D 11 hardware.
- 7 draw calls por frame.
- Perfil estándar: 5 s de warm-up global fuera de estadísticas y 10 + 12 + 12 + 15 = **49 s medidos**.
- FPS reales y 1% Low.
- GPU timestamp queries cuando el driver las valida.
- `REAL_OR_NA` / `REAL_FPS_OR_NA_ONLY`.
- Seguridad térmica y propagación de `SAFETY_STOP`.
- Persistencia: `resultados/benchmark_gpu_v19_ultimo_resultado.json`.

## Pruebas

- Suite V197 + regresiones V19 + seguridad térmica: **27 PASS**, 2 guards históricos excluidos por exigir hashes V13 antiguos.
- `tests/test_unified_live_health_agent_instant.py`: **PASS**.
- `python -m compileall -q core gui tools`: **PASS**.

Los guards históricos excluidos no representan regresiones actuales: verifican literalmente un workload V13 anterior.
