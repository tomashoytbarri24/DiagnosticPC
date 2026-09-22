# VALIDACIÓN V199 — Benchmark V19 Knowledge Clarity

## Alcance
V199 es una versión de UX/conocimiento. El workload del Benchmark GPU V19 debe permanecer byte por byte idéntico a V198.

## Principios validados
- Una ejecución completa no se convierte automáticamente en "rendimiento correcto".
- Si el 1% Low queda muy alejado del FPS medio en una escena, CorePulse lo presenta como entrega irregular y recomienda repetir antes de atribuirlo al hardware.
- CPU/RAM/SSD explican integridad, estabilidad y temperatura con frases cortas.
- La vista Resumen prioriza una conclusión global y evita repetir las mismas explicaciones en cada tarjeta.
- N/A continúa significando no evaluable, nunca un dato estimado.

## Benchmark
GPU V19 sin cambios: 49 s medidos, wall-clock, FPS/1% Low reales, timestamps GPU y seguridad térmica.

## Resultado de regresión
- Pruebas específicas V199: 5 PASS.
- Regresiones funcionales vigentes seleccionadas: 21 PASS.
- `test_unified_live_health_agent_instant.py`: PASS.
- `compileall core gui tools`: PASS.
- Guards históricos que exigen literalmente V197/V198 o hashes V13 no se consideran regresiones actuales.

## Hashes V19 conservados
- `core/directx_scene.py`: `21716b2013cfcee87330f81620a71791952024474af2e734c30d4c7fa6f32e2b`
- `core/directx_benchmark.py`: `754b46a53e379db6bb4cec1b109a4231b86f391395067a0efa28ac6495f68cd7`
- `core/benchmark_engine.py`: `255be8fc4267944472a060e8fd793bc5cbb2471cd3d692911a5bb3d9d0e56891`
