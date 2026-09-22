# Validación V184 — Benchmark GPU V16 Visual Cleanup

Resultado de validación: **PASS**.

- `py_compile`: PASS en versión, engine, renderer DirectX, escena, presentación, Centro de Salud y herramienta manual V16.
- Regresiones relevantes V179/V180/V181 + pruebas V184: **22/22 PASS**.
- Perfil estándar: **10 + 12 + 12 + 15 = 49 s medidos**, sin cambios.
- Warm-up inicial: **5 s**, sin cambios.
- Malla de agua: **idéntica byte-a-byte en datos generados** respecto a V183; 72.962 triángulos.
- Árbol: **328 triángulos**, mismo conteo que V183; geometría determinista y finita.
- Shader de hojas: una única `NoiseTex.Sample` en el bloque de follaje; el nuevo recorte no añade texture fetches.
- `core/benchmark_telemetry.py`: SHA-256 idéntico a V183.
- `core/thermal_throttling.py`: SHA-256 idéntico a V183.
- `gui/stable_scroll.py`: SHA-256 idéntico a V183.
- Scan de metadata runtime antigua V14/V15 en el flujo V16: sin coincidencias de IDs/modes/policies/labels obsoletos.
- JSON vigente: `resultados/benchmark_gpu_v16_ultimo_resultado.json`.

Los tests históricos que fijan literalmente una versión o hashes de workloads anteriores no se usan como criterio de V184 porque el workload visual cambia deliberadamente a V16.
