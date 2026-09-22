# Validación V189 — Benchmark GPU V16 Professional Integration

## Contrato

V189 es una versión de presentación/UX. El workload GPU medido debe permanecer idéntico a V188.

## Hashes V16 preservados

- `core/directx_benchmark.py`: `a9106f3157a0a7e8cc54e4924d5afe2c0d99c78823a45c1acdb86b90c3d88437`
- `core/directx_scene.py`: `879f7a664d2616fa5485477e9475393bf11bd5b2d082cfaf2bf934ac5c05f5ee`
- `core/benchmark_engine.py`: `c77426c5b56632cda58c13af0a032470656ef3ae55e81ac209a8ea4d5fb40fe5`

## Validaciones realizadas

- `py_compile`: PASS.
- Tests específicos V189: 6 PASS.
- Regresiones funcionales vigentes V180/V181/V184/V185/V186/V187/V188/V189: 36 PASS.
- Los tests históricos que exigen números de versión anteriores, hashes V13/V180 o textos UI reemplazados se consideran guards históricos y no regresiones actuales.

## Política de datos

- `REAL_OR_NA` preservado.
- HUD: FPS sólo si DirectX ya reportó una lectura real.
- Warm-up/settle: `N/A`.
- No se alteran wall-clock, frametimes, 1% Low, timestamps GPU ni seguridad térmica.

## Verificación pendiente en Windows

Este entorno no ejecuta la ventana Direct3D 11 real. Debe confirmarse visualmente en Windows:
1. HUD redondeado/azul-cian correctamente superpuesto.
2. Cursor no visible durante la fase GPU.
3. Restauración del cursor al cerrar DirectX.
4. Primera apertura del panel Benchmark perceptiblemente más clara.
