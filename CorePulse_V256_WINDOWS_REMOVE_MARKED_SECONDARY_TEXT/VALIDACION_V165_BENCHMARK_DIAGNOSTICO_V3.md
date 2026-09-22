# Validación V165 — Benchmark Diagnóstico V3

## Objetivo
Reemplazar el benchmark V2 por una suite técnica auditable sin depender de una escena 3D decorativa.

## Contrato
- REAL_OR_NA: si una prueba no se puede ejecutar o verificar, no se inventa un resultado.
- CPU/RAM/SSD publican medianas de 3 muestras.
- CV alto se conserva como evidencia pero se marca VARIABLE/PARTIAL.
- GPU corre por áreas técnicas y puede ejecutarse con ventana oculta.
- Benchmark y stress test siguen separados.

## Pruebas ejecutadas en este entorno
- `pytest -q tests/test_v165_benchmark_diagnostic_v3.py` -> 5/5 PASS.
- `python -m compileall -q core gui` -> PASS.
- CPU V3 smoke: 3 muestras válidas + integridad zlib PASS.
- RAM V3 smoke: 3 muestras válidas + integridad byte a byte PASS.
- Suite quick CPU+RAM -> status OK.

## Pendiente de validación física en Windows
- GPU OpenGL real, renderer, VSync y throughput por fase.
- SSD NO_BUFFERING/WRITE_THROUGH + Random 4K QD1.
- Repetibilidad en hardware real durante el Diagnóstico Total.

## Archivos principales modificados
- core/benchmark_engine.py
- core/visual_benchmark.py
- core/benchmark_presentation.py
- gui/health_center_panel.py
- gui/benchmark_history_panel.py
- core/version.py
- core/complete_diagnostic.py
