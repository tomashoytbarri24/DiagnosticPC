# Validación V179 — Thermal Audit + UI Closure

## Alcance
V179 parte de V178 Benchmark GPU V13 y no modifica el workload DirectX ni el motor de benchmark.

## Integridad del workload
SHA-256 idéntico V178 → V179:

- `core/directx_benchmark.py`: `2981c9dda17e691625b6248879b42bcf0816fd594867705f50c41703987a415c`
- `core/directx_scene.py`: `dc6a9225112dd3c8b71daef1dc610427921ea2d92e11f1ee30625342b14e2b0f`
- `core/benchmark_engine.py`: `a8318a6eacccbda282ffa6bb6282ab3797225d5a99dd5da7f2719a5a98e25f68`

Por tanto, escenas, geometría, shaders, tiempos, warm-up, settle, prime, cálculo FPS/1% Low y timestamps GPU permanecen iguales a V178/V13.

## Cambios validados

1. La UI no puede mostrar `LISTO` mientras exista progreso parcial de una ejecución (caso 97 %).
2. El callback final ya no fuerza un segundo `_render()` inmediato; `_async` agenda un único render tras publicar el resultado.
3. `telemetry.thermal_audit` conserva evidencia REAL_OR_NA:
   - CPU: pico, muestras >=95 °C, tramo observado por timestamps y distancia mínima a TjMax.
   - GPU del renderer: pico core/hotspot, muestras >=88 °C, límites térmicos sólo si el sensor los reporta y margen mínimo observado.
4. Una distancia real a TjMax de `0.0 °C` se conserva como valor válido.
5. Un límite térmico GPU realmente reportado puede activar la parada tras 3 muestras consecutivas; si no existe, se conserva el fallback extremo sostenido de 95 °C.
6. Los tramos térmicos no interpolan el estado entre muestras.

## Pruebas

Comando:

`python -m unittest tests.test_v177_benchmark_ui tests.test_v178_benchmark_v13 tests.test_v179_thermal_ui_closure -v`

Resultado: **13/13 PASS**.

Además, `tests.test_startup` confirmó imports/versionado/runtime parsing: **PASS**.

## Validación pendiente en Windows real

La ejecución real sigue siendo necesaria para confirmar el comportamiento visual de cierre y poblar la auditoría con los sensores del equipo. Tras ejecutar `Probar_Benchmark_GPU_V13.bat` o el benchmark desde CorePulse, revisar:

`resultados/benchmark_gpu_v13_ultimo_resultado.json`

Campo principal nuevo:

`telemetry.thermal_audit`
