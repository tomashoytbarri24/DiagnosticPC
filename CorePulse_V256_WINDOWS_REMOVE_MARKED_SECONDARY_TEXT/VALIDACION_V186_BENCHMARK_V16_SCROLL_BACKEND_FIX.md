# Validación V186 — Benchmark GPU V16 Scroll Backend Fix

- `core/directx_benchmark.py`: SHA-256 `a9106f3157a0a7e8cc54e4924d5afe2c0d99c78823a45c1acdb86b90c3d88437`
- `core/directx_scene.py`: SHA-256 `879f7a664d2616fa5485477e9475393bf11bd5b2d082cfaf2bf934ac5c05f5ee`
- `core/benchmark_engine.py`: SHA-256 `c77426c5b56632cda58c13af0a032470656ef3ae55e81ac209a8ea4d5fb40fe5`
- Los tres coinciden exactamente con V185.
- Pruebas V186: 6 PASS.
- Regresión V185 (sin guard literal de versión): 3 PASS.
- Regresión V184 (sin guard literal de versión): 6 PASS.
- Seguridad térmica/orquestación V180-V181: 10 PASS (1 guard histórico de hash V13 excluido).
- Auditoría térmica V179: 6 PASS.
- Total vigente ejecutado: 31 PASS.
- `py_compile`: PASS para los archivos modificados.

La validación visual definitiva del ghosting debe hacerse en Windows mediante una ejecución real y scroll de la sección de resultados.
