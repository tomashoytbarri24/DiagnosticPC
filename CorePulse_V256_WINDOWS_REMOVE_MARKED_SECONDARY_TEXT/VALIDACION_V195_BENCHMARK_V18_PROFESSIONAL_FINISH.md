# VALIDACIÓN V195 — BENCHMARK GPU V18 PROFESSIONAL FINISH

## Contratos
- Aplicación: V195.
- Benchmark GPU: V18.
- Resultado: `resultados/benchmark_gpu_v18_ultimo_resultado.json`.
- Standard: 10 + 12 + 12 + 15 = 49 s medidos, con 5 s de warm-up global y settle por escena.
- VSync OFF, FPS/1% Low reales, timestamps GPU cuando el driver los valida, `REAL_OR_NA`.

## Validación local
- `py_compile`/`compileall`: PASS.
- Pruebas específicas V195: 8 PASS.
- Regresiones térmicas relevantes V179–V181: 16 PASS (se excluye exclusivamente el guard histórico que exige hashes V13/V180).
- Persistencia V18 probada sin sobrescribir un archivo V17 existente.
- Dashboard: páginas preconstruidas y alternadas sin full rebuild.
- Historial: lectura fuera del hilo Tk con datos precargados.

## Limitación del entorno de build
El renderer Direct3D 11 visible debe validarse en Windows real mediante video/JSON; este entorno no ejecuta una sesión D3D11 visible.
