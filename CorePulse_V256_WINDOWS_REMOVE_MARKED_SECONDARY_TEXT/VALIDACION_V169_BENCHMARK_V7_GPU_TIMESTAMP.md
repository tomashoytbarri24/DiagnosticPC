# CorePulse V169 — Benchmark GPU V7 · Timestamp GPU D3D11

## Objetivo

Corregir la principal limitación observada en V168: el FPS/frametime visible era real desde la aplicación, pero no aislaba cuánto tardó la GPU en ejecutar el command stream. V169 conserva el benchmark Direct3D 11 progresivo y añade medición temporal dentro de la propia GPU mediante `D3D11_QUERY_TIMESTAMP` delimitado por `D3D11_QUERY_TIMESTAMP_DISJOINT`.

## Cambios

- Nueva metodología GPU: `COREPULSE_GPU_DIRECTX11_SCENES_V7`.
- Nuevo método global: `COREPULSE_BENCHMARK_7_GPU_TIMESTAMP`.
- Pool pre-creado de 64 juegos de queries para no crear objetos durante la ventana medida.
- `Begin(DISJOINT)` + `End(TIMESTAMP start)` antes del frame y `End(TIMESTAMP end)` + `End(DISJOINT)` al terminar los draws.
- Lectura no bloqueante durante la escena; drenaje de queries fuera de la ventana medida.
- Si una query es `Disjoint`, falla o el pool se agota, esa muestra se descarta. No se estima ni interpola.
- Nuevas métricas por escena: GPU avg/median/p95/p99/min/max, cantidad de muestras, cobertura, queries descartadas y disjoint.
- CPU/Present frametime se conserva separado del GPU frametime.
- La pestaña Benchmark muestra ambos tiempos, no los mezcla.

## Corrección visual

- La formación de jets fue alejada de la trayectoria de cámara para evitar que un avión atraviese el near-field y ocupe gran parte de la pantalla.
- Jet aumentado de 14 a 18 segmentos radiales.
- Nubes más densas y ubicadas a mayor altura para reducir intersecciones con cámara.
- El workload publicado se recalcula desde los meshes actuales.

## Validación ejecutada en entorno de construcción

- `py_compile`: 402 archivos Python, 0 errores.
- Suite DirectX/timing dirigida: 20 pruebas PASS.
- Test del conversor de timestamp: frecuencia 1 MHz, diferencia 5000 ticks => 5.0 ms PASS.
- Verificación de constantes `D3D11_QUERY_TIMESTAMP=2`, `D3D11_QUERY_TIMESTAMP_DISJOINT=3` y slots `Begin=27`, `End=28`, `GetData=29` PASS.
- Política REAL_OR_NA preservada.

## Validación que debe hacerse en Windows real

Este entorno no dispone de Direct3D 11 físico. Ejecutar `Probar_Benchmark_GPU_V7.bat` en el PC objetivo y comprobar en `benchmark_gpu_v7_ultimo_resultado.json`:

- `gpu_timing_available = true`
- `gpu_frame_time_avg_ms` con valor real en cada escena
- `gpu_sample_coverage` idealmente cercano a 1.0
- `gpu_query_disjoint_frames` y `gpu_query_dropped_frames`
- progresión Low → Medium → High en perfil quick o Low → Medium → High → Extreme en estándar

Una lectura `gpu_frame_time_* = N/A` debe conservarse como N/A; nunca se sustituye por CPU frametime.
