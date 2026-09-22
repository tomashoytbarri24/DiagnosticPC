# V203 — Windows Mainline · Benchmark GPU V23 · Boat / Fire / Smoke Visibility

## Objetivo
Corregir tres observaciones del uso real:

1. El barco seguía viéndose extraño.
2. La fogata de Extreme no se apreciaba.
3. El humo debía moverse claramente en tiempo real y ser más visible.

## Cambios aplicados
- `core/directx_scene.py`
  - Se añade `fire_instances`.
  - Extreme ahora usa `smoke_instances=3` y `fire_instances=2`.
  - `build_boat()` se rediseña con una geometría más limpia.
- `core/directx_benchmark.py`
  - Benchmark GPU sube a **V23**.
  - El barco navega por un corredor más central y legible.
  - La fogata usa un draw call propio (`type 9`) con flicker visible.
  - El humo usa varias instancias animadas con deriva y ascenso en tiempo real.
- `core/benchmark_engine.py`
  - El archivo vigente pasa a `benchmark_gpu_v23_ultimo_resultado.json`.

## Política
- Sin datos inventados.
- Si una métrica no puede medirse, queda en `N/A`.
- No cambia el contrato de 49 s medidos en estándar.
