# Validación V175 — Benchmark V12 Wall-Clock Deterministic

## Problema corregido
En V174 la cámara/animación durante la ventana medida usaba la suma acumulada de `render + Present`. El trabajo deliberadamente excluido del frametime (query readback, callbacks, telemetría y message pump) sí consumía tiempo real pero no avanzaba esa variable. El resultado observable era una escena que podía parecer entrar en cámara lenta y una ventana 3D más larga de lo esperado.

## V175
- La condición de fin de fase usa `time.perf_counter() - measure_wall_start >= measure_seconds`.
- El tiempo enviado al shader/cámara usa ese mismo `wall_elapsed`.
- `frame_ms` conserva exclusivamente `render_frame + Present`.
- Timestamp GPU D3D11 se mantiene independiente.
- El callback de progreso se limita a 10 Hz y queda fuera del frametime.
- No se eliminan frames lentos reales de 1% Low/p95/p99.

## Tiempos estándar
- Warm-up global: 5.00 s (fuera de estadísticas).
- Valle: settle 0.75 s + 10.00 s medidos.
- Bosque: settle 1.00 s + 12.00 s medidos.
- Lago: settle 1.00 s + 12.00 s medidos.
- Extreme: settle 1.25 s + 15.00 s medidos.
- Medición por reloj de pared: 49.00 s.
- Warm-up + settle + medición: 58.00 s, más 8 prime frames por escena y overhead final de queries.

## Regla de interpretación
Una GPU más lenta debe producir menos FPS y movimiento menos fluido, pero la cámara debe recorrer la misma trayectoria en el mismo tiempo real. Los resultados siguen siendo REAL_OR_NA y no usan lookup por modelo ni score sintético.

## Límite de validación local
El entorno de construcción no ejecuta Direct3D 11 físico. Se valida sintaxis, invariantes temporales, integración, fake-COM y regresiones; la validación visual final requiere Windows + GPU real.

## Validación ejecutada en construcción
- `python -m compileall -q .`: PASS.
- `tests/test_v175_benchmark_v12_wallclock_deterministic.py`: PASS.
- `tests/test_v174_directx_depth_state_hotfix.py`: PASS.
- `tests/test_v168_directx_fake_com_smoke.py`: PASS.
- Total focalizado V175/runtime: **9/9 PASS**.

El archivo histórico `tests/test_v161_benchmark_diagnostic.py` no se usa como criterio de aceptación de V175: actualmente contiene expectativas de un flujo diagnóstico antiguo y pruebas GUI que dependen de `customtkinter` no instalado en el entorno Linux de construcción. Sus fallos no corresponden al cambio temporal V175.
