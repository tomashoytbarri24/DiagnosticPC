# V201 — Windows Mainline · Benchmark GPU V21 · Scene Rebalance + Result Usability

## Objetivo

Continuar la rama Windows desde V200 y corregir dos frentes observados en uso real:

1. La escena GPU seguía viéndose sobrecargada por la cantidad de aviones.
2. El resultado debía priorizar una lectura más rápida y menos tediosa antes del detalle.

## Cambios aplicados

- `core/directx_scene.py`
  - El avión pasa a **1 instancia** en todas las escenas.
  - Se agrega `boat_instances` y `smoke_instances` al workload.
  - Se añade `build_boat()` y se actualiza `level_workload()`.
- `core/directx_benchmark.py`
  - Benchmark GPU sube a **V21**.
  - Se integra un **barco navegando** y **humo de fogata** en Extreme.
  - Se conserva la ventana DirectX dedicada, VSync OFF, wall-clock y timestamps GPU.
- `gui/health_center_panel.py`
  - La pestaña inicial de resultados pasa a mostrarse como **Resumen rápido**.
  - Se añade una franja de **Lectura rápida** con lo esencial antes del detalle.
  - La conclusión limita la repetición y reduce densidad visual.
- `core/benchmark_engine.py`
  - Se actualiza el archivo vigente a `benchmark_gpu_v21_ultimo_resultado.json`.
  - V20 y anteriores quedan como alias de compatibilidad hacia la ruta vigente.

## Política

- Sin datos inventados.
- Si una métrica no existe o no puede medirse, queda en `N/A`.
- No se cambió el contrato de 49 segundos medidos en GPU estándar.

## Validación sugerida en Windows

1. Ejecutar `Probar_Benchmark_GPU_V20.bat` o la app completa y revisar la escena:
   - 1 avión visible y legible.
   - 1 barco navegando.
   - En Extreme, humo/fogata en isla.
2. Confirmar que la primera vista de resultados sea más rápida de leer.
3. Confirmar guardado en `resultados/benchmark_gpu_v21_ultimo_resultado.json`.
