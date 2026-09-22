# CorePulse V167 — Validación Benchmark V5 DirectX 11

## Objetivo
Reemplazar la ruta GPU del benchmark por una prueba gráfica de alto nivel Direct3D 11, visible, determinista y auditable. La escena renderizada ES la carga medida; no existe una animación decorativa separada del workload.

## Escenas estándar
| Escena | Terreno | Árboles | Rocas | Jets | Nubes | Iter. shader | Muestras textura | Warm-up | Medición |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Low | 72×72 | 160 | 70 | 3 | 24 | 4 | 2 | 2.0 s | 8.0 s |
| Medium | 112×112 | 520 | 220 | 7 | 48 | 8 | 4 | 2.0 s | 8.0 s |
| High | 160×160 | 1500 | 520 | 12 | 88 | 16 | 8 | 2.5 s | 8.0 s |
| Extreme | 224×224 | 3500 | 1100 | 18 | 140 | 28 | 12 | 3.0 s | 8.0 s |

Tiempo GPU estándar objetivo: 41.5 s, de los cuales 9.5 s son calentamiento excluido y 32 s son medición.

## Métricas publicadas
- FPS de frames realmente presentados con `Present(0, 0)` y VSync OFF.
- 1% Low derivado de los frame times medidos.
- frametime promedio, p95 y p99.
- resolución efectiva, API, feature level, adaptador y VRAM dedicada reportada por DXGI.
- configuración exacta de cada workload: objetos, triángulos aproximados, iteraciones de shader y muestras de textura.
- telemetría disponible durante warm-up y medición.

El tiempo GPU mediante timestamp queries queda **N/A** en V167 hasta validarlo físicamente en hardware Windows. No se estima.

## Política REAL_OR_NA
No hay fallback silencioso al benchmark OpenGL anterior. Si Direct3D 11 no puede inicializarse, la GPU queda ERROR/N/A y se informa la causa. El antiguo workload OpenGL permanece únicamente como carga heredada del stress test; no determina el resultado del Benchmark V5.

## Validación realizada en el entorno de construcción
- `tests/test_v167_benchmark_v5_directx_scenes.py`: 6/6 PASS.
- complejidad estrictamente creciente: PASS.
- warm-up separado de la ventana de medición: PASS por estructura/automatización.
- agregación FPS/1% low/frametimes desde muestras reales: PASS.
- adaptación del resultado al motor principal sin score sintético: PASS.
- compilación Python del árbol del proyecto: PASS.
- ruta no-Windows: `UNAVAILABLE` + valor `None`: PASS.

## Validación física pendiente y obligatoria
El entorno de construcción no es Windows y no puede ejecutar Direct3D 11. Por tanto, antes de considerar V167 candidata estable se debe ejecutar en un PC Windows real:

1. `Probar_Benchmark_GPU_V5.bat`.
2. Comprobar que las cuatro escenas se dibujen correctamente y sin artefactos graves.
3. Confirmar que cada escena dura aproximadamente su warm-up + 8 s de medición.
4. Confirmar que Low → Medium → High → Extreme aumenta visual y técnicamente la complejidad.
5. Revisar `benchmark_gpu_v5_ultimo_resultado.json`.
6. Repetir tres veces con el PC en condiciones equivalentes y revisar estabilidad.

Si DirectX falla, no sustituir el resultado con OpenGL ni con valores inferidos por modelo de GPU.
