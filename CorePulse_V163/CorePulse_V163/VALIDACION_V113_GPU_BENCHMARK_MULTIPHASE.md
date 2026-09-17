# V113 — GPU Benchmark Multi-Phase

## Objetivo
Convertir el benchmark visual 3D principal en una prueba por áreas de GPU sin inventar cargas que el motor todavía no ejecuta.

## Fases implementadas
1. **Geometría**: malla 3D procedural, múltiples draw calls, transformaciones y triángulos reales.
2. **Fill / fragmentos**: quads de pantalla con overdraw y blending real.
3. **Texturas / VRAM**: texturas OpenGL procedurales reales, múltiples recursos y muestreo repetido. La cifra de MB indica memoria solicitada por la carga, no capacidad física de la GPU.
4. **Carga combinada**: geometría + muestreo de texturas en una misma secuencia de frame.

## Métricas
- FPS promedio por fase calculado desde frametimes reales.
- 1% Low por fase usando el 1% de frames más lentos.
- Frametime promedio, P95 y P99 por fase.
- Telemetría CPU/GPU/RAM/VRAM real separada por fase cuando el sensor existe.
- La fase `combined` es el resultado principal del benchmark.

## Política de evidencia
- `REAL_OR_NA`.
- `REAL_FPS_OR_NA_ONLY`.
- Sin random, simulación, offsets ni rankings inventados.
- Shaders programables, Compute y Ray Tracing permanecen fuera del resultado hasta que el motor ejecute cargas reales específicas.

## Seguridad
Se preserva el corte preventivo cuando la CPU alcanza 96 °C o la GPU 92 °C.

## Validación estática
- `test_gpu_benchmark_multiphase_v113.py`: PASS.
- `test_visual_3d_benchmark_v113.py`: PASS.
- `test_visual_benchmark_primary_v113.py`: PASS.
- `test_benchmark_preconfiguration_v113.py`: PASS.
- `test_benchmark_main_sidebar_v113.py`: PASS.
- `py_compile`: PASS.

La ejecución gráfica Win32/OpenGL debe validarse finalmente en Windows con GPU acelerada por hardware.
