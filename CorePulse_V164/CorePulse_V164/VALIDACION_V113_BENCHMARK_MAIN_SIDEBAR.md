# V113 — Benchmark principal independiente

## Objetivo
Mover el benchmark visual 3D fuera de Gaming y publicarlo como una función principal independiente de CorePulse.

## Cambios
- Nuevo botón lateral `Benchmark` inmediatamente después de `Resumen`.
- Nueva ruta interna `benchmark` con estado activo propio en el sidebar.
- Nueva página `gui/benchmark_panel.py` dedicada exclusivamente al benchmark visual.
- Gaming ya no muestra tarjetas, accesos rápidos ni subrutas de Benchmark.
- Centro de Salud > Rendimiento ya no describe el benchmark como parte de Gaming.
- Se reutiliza el motor visual 3D real existente y su telemetría REAL_OR_NA / REAL_FPS_OR_NA_ONLY.

## Validación
- `tests/test_benchmark_main_sidebar_v113.py`: PASS.
- `tests/test_benchmark_preconfiguration_v113.py`: PASS.
- `tests/test_visual_3d_benchmark_v113.py`: PASS.
- `tests/test_visual_benchmark_primary_v113.py`: PASS.
- `tests/test_dashboard.py`: PASS.
- `python -m compileall -q .`: PASS.

Nota: algunos tests históricos de V100/V103 conservan aserciones de versión antiguas y no forman parte de esta validación de V113.
