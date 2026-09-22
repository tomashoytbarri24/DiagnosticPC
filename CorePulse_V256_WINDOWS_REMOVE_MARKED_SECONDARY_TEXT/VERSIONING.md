## V200 — Benchmark GPU V20 · Result Clarity + Aircraft Framing

- Aplicación: V200.
- Benchmark GPU: **V20**.
- Motivo del salto: cambia la transformación espacial/tamaño aparente de la formación de jets, por lo que V20 no se mezcla como equivalente con V19.
- Geometría base y conteo de instancias/draw calls se mantienen.
- Resultado persistente: `resultados/benchmark_gpu_v20_ultimo_resultado.json`.
- Tiempos medidos estándar: **10 + 12 + 12 + 15 = 49 s**.

## V199
- Aplicación: V199.
- Benchmark GPU: V19 (sin cambios de workload).
- Resultado persistente: `resultados/benchmark_gpu_v19_ultimo_resultado.json`.

## V198 — Benchmark GPU V19 · Knowledge Layer

- Versión de aplicación: `198`.
- Benchmark GPU: permanece **V19**.
- No cambia escena, geometría, HLSL, draw calls, temporización ni fórmula de medición respecto de V197.
- Resultado persistente: `resultados/benchmark_gpu_v19_ultimo_resultado.json`.
- Tiempos medidos estándar: **10 + 12 + 12 + 15 = 49 s**.
- Cambio exclusivo de presentación/interpretación: `Lectura CorePulse` usa estado, integridad, estabilidad y temperatura realmente observados.

## V197 — Benchmark GPU V19 · UX Closure

- Versión de aplicación: `197`.
- Benchmark GPU: permanece **V19**.
- No cambia escena, geometría, HLSL, draw calls, temporización ni fórmula de medición respecto de V196.
- Resultado persistente: `resultados/benchmark_gpu_v19_ultimo_resultado.json`.
- Tiempos medidos estándar: **10 + 12 + 12 + 15 = 49 s**.
- Cambios exclusivos de UX/legibilidad/primer render del Historial.

## V196 — Benchmark GPU V19 · Visual/UX Finish

- Versión de aplicación: `196`.
- Benchmark GPU: **V19**.
- Cambio metodológico: el workload visual cambia respecto a V18, por lo que sus FPS no se mezclan como equivalentes.
- Resultado persistente: `resultados/benchmark_gpu_v19_ultimo_resultado.json`.
- Tiempos medidos estándar: **10 + 12 + 12 + 15 = 49 s**.
- 7 draw calls por frame.
- `REAL_OR_NA`, wall-clock, GPU timestamp y seguridad térmica continúan vigentes.

## V195 — Benchmark GPU V18 · Professional Finish

- Versión de aplicación: `195`.
- Benchmark GPU: **V18**.
- Motivo del salto metodológico: cambia la presentación espacial del workload de jets (formación/posición/niebla), por lo que no se mezclan FPS con V17.
- Resultado persistente: `resultados/benchmark_gpu_v18_ultimo_resultado.json`.
- Tiempos estándar preservados: 5 s warm-up global + settle por escena + **49 s medidos**.
- La versión de metodología se define una sola vez en `core/benchmark_version.py` para mantener HUD/renderer/engine/historial sincronizados.

## V193 — Benchmark GPU V16 · Clarity Finish

- Versión de aplicación: `193`.
- Benchmark GPU: permanece **V16**; escenas, shaders y temporización no cambian.
- Resultado persistente: `resultados/benchmark_gpu_v16_ultimo_resultado.json`.
- Cambios exclusivos de UX: transición atómica de resultados, detalle progresivo, bordes y carga de Historial.
- El siguiente cambio material de agua/aviones/vegetación debe versionarse como GPU V17.

## V192 — Benchmark GPU V16 · Static Results

- Versión de aplicación: `192`.
- Benchmark GPU: permanece **V16**; no cambian escena, shaders ni temporización.
- Resultado persistente: `resultados/benchmark_gpu_v16_ultimo_resultado.json`.
- Cambio exclusivo de arquitectura UI: resultados estáticos + Historial progresivo estable.
- El siguiente cambio material del escenario 3D debe versionarse como GPU V17.

## V191 — Benchmark GPU V16 · UX Refinement
- Versión de aplicación: `191`.
- Método GPU V16 sin cambios.
- Correcciones de configuración, historial progresivo y evidencia térmica.
- JSON: `resultados/benchmark_gpu_v16_ultimo_resultado.json`.
- Siguiente cambio visual material del workload deberá versionarse como GPU V17.

## V190 — Benchmark GPU V16 · CorePulse Finish

- Versión de aplicación: `190`.
- Benchmark GPU: sigue siendo **V16**.
- Resultado: `resultados/benchmark_gpu_v16_ultimo_resultado.json`.
- `directx_scene.py` y `benchmark_engine.py` son idénticos a V189.
- El HLSL V16 es idéntico a V189.
- `directx_benchmark.py` cambia únicamente en manejo de cursor/ventana (`WM_SETCURSOR` y `SetCursor(None)`), fuera de la región cronometrada; no cambia el workload medido.
- Cambios restantes: presentación, tipografía, bordes, jerarquía de resultados y severidad visual instantánea.


## V189 — Benchmark GPU V16 · Professional Integration

- Versión de aplicación: `189`.
- Benchmark GPU: sigue siendo **V16** porque el workload medido no cambia.
- Resultado: `resultados/benchmark_gpu_v16_ultimo_resultado.json`.
- Cambios exclusivamente de HUD, cursor, estilo del dashboard y carga inicial.
- Los hashes de `directx_benchmark.py`, `directx_scene.py` y `benchmark_engine.py` deben coincidir con V188.


## V188 — Benchmark GPU V16 UX/HUD Fix

- App: V188.
- Método GPU: permanece V16 porque escenas, shaders, timing y `benchmark_engine` son byte-identical a V187.
- HUD y cursor son presentación externa a la región cronometrada.
- Resultado persistente: `resultados/benchmark_gpu_v16_ultimo_resultado.json`.

## V187 — Benchmark V16 · UX Dashboard
- Mantiene Benchmark GPU V16 y `benchmark_gpu_v16_ultimo_resultado.json`.
- Cambio exclusivo de experiencia de uso y composición de la página Benchmark.
- Primera entrada progresiva, historial lazy y resultados con divulgación progresiva.
- No cambia escenas, shaders, 49 s medidos, FPS/1% Low, timestamps GPU ni seguridad térmica.

## V186 — Benchmark V16 · Scroll Backend Fix
- Mantiene Benchmark GPU V16 y `benchmark_gpu_v16_ultimo_resultado.json`.
- Cambio exclusivo de infraestructura UI en la página Benchmark.
- No cambia escenas, shaders, tiempos ni seguridad térmica.

## V185 — Benchmark V16 · UI Ghost Fix
- Benchmark GPU V16 preservado byte a byte en renderer/escena/engine.
- Repaint fuerte de Windows también para scroll con rueda, manteniendo throttle por frame.
- Resultado continúa en `benchmark_gpu_v16_ultimo_resultado.json`.

## V184 — Benchmark V16 · Visual Cleanup
- Método GPU V16 separado de V15 por cambio material del recorte/orientación de follaje.
- Resultado independiente: `benchmark_gpu_v16_ultimo_resultado.json`.
- Conserva tiempos medidos, agua, wall-clock, timestamps GPU y seguridad térmica.

## V183 — Benchmark V15 · Visual Polish

- Versión 183; primer cambio visual posterior a la estabilización V181.
- Método GPU V15 separado de V13 por cambio material de shaders/geometría.
- Mismos tiempos objetivo del perfil estándar: 5 s warm-up global + settle + 49 s medidos.
- JSON: `resultados/benchmark_gpu_v15_ultimo_resultado.json`.

## V181 — Benchmark V13 · Safety propagation/UI settle

- Versión 181; escenas DirectX V13 sin cambios.
- Stop térmico propagado al renderer GPU.
- Auditoría del gatillo TjMax y repintado de resultados reforzado.

## V180 — Benchmark V13 · Safety/UI atomic

- Versión 180; método GPU V13 sin cambios.
- Base directa: V179.
- Siguiente etapa tras validar V180: pulido visual de agua/vegetación.

## V179 — Benchmark V13 · Thermal/UI closure

- Versión 179; método GPU V13 sin cambios.
- Corrige transición final de UI y estado LISTO/progreso.
- Añade auditoría térmica observacional al JSON V13 sin modificar el workload.
- JSON: `resultados/benchmark_gpu_v13_ultimo_resultado.json`.

## V178 — Benchmark V13

- Versión 178; método GPU `COREPULSE_GPU_DIRECTX11_SCENES_V13_WALLCLOCK_DETERMINISTIC`.
- Cambia carga gráfica: no comparar FPS directamente con V12.
- JSON: `resultados/benchmark_gpu_v13_ultimo_resultado.json`.
- Perfil temporal V12 y presentación V177 conservados.

## V177 — Presentación final del benchmark

- Versión de aplicación: `177`.
- Método V12 intacto; cambios exclusivamente de presentación y estado de interfaz.
- Prueba: `python -m unittest tests.test_v177_benchmark_ui -v`.

## V176 — Persistencia del último resultado GPU V12

- Versión de aplicación: `176`.
- Conserva sin cambios el método GPU V12 y su reloj de pared determinista.
- Guarda el resultado GPU correcto en `resultados/benchmark_gpu_v12_ultimo_resultado.json`.
- Resuelve la raíz desde el proyecto en Python y desde la carpeta del ejecutable en PyInstaller.
- Política: `REAL_OR_NA`; no genera métricas ni reemplaza ausencias por estimaciones.

## V175 — Benchmark V12 Wall-Clock Deterministic

- Versión de aplicación: `175`.
- Método general: `COREPULSE_BENCHMARK_12_WALLCLOCK_DETERMINISTIC_GPU_TIMESTAMP`.
- GPU: `COREPULSE_GPU_DIRECTX11_SCENES_V12_WALLCLOCK_DETERMINISTIC`.
- GPU estándar: 49 s de medición por reloj de pared (10+12+12+15), con warm-up/settle/prime fuera de estadísticas.
- Cámara/animación: tiempo de pared real. Frametime: sólo render + Present. GPU time: D3D11 timestamp queries.
- Historial V12 no debe mezclarse numéricamente con V11: cambió la semántica temporal de la prueba.
- Validación: `VALIDACION_V175_BENCHMARK_V12_WALLCLOCK_DETERMINISTIC.md`.

## V173 — Benchmark V11 Realistic Polish + Audited Steady-State Timing

- Versión de aplicación: `173`.
- Método general: `COREPULSE_BENCHMARK_11_REALISTIC_POLISHED_GPU_TIMESTAMP`.
- GPU: `COREPULSE_GPU_DIRECTX11_SCENES_V11_REALISTIC_POLISHED`.
- GPU estándar: Valle/Bosque/Lago/Extreme, 49 s efectivos medidos + warm-up/settle + 8 prime frames por escena fuera de estadísticas.
- El historial V11 no debe mezclarse numéricamente con V10/V9: cambió la geometría, materiales y preparación de la ventana medida.
- Validación: `VALIDACION_V173_BENCHMARK_V11_REALISTIC_POLISHED.md`.

## V172 — Benchmark V10 Realistic Materials + Isolated Frametime

- Versión de aplicación: `172`.
- Método general: `COREPULSE_BENCHMARK_10_REALISTIC_ISOLATED_GPU_TIMESTAMP`.
- GPU: `COREPULSE_GPU_DIRECTX11_SCENES_V10_REALISTIC_ISOLATED`.
- GPU estándar: Valle/Bosque/Lago/Extreme, 49 s efectivos medidos + warm-up/settle fuera de estadísticas.
- El historial V10 no debe mezclarse numéricamente con V9/V8/V7: cambió la geometría, materiales y metodología temporal.
- Validación: `VALIDACION_V172_BENCHMARK_V10_REALISTIC.md`.
