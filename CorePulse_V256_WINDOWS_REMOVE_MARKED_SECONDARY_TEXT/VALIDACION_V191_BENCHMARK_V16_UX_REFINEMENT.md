# Validación V191 — Benchmark GPU V16 · UX Refinement

## Alcance

V191 modifica únicamente presentación/UX del panel Benchmark e Historial. No cambia el workload GPU V16.

## Evidencia del video V190

- Cursor de espera: no visible dentro de la escena DirectX.
- HUD: visible, legible y estable.
- Resultados: sin ghosting evidente en Resumen/GPU 3D/Sistema/Evidencia durante la revisión.
- Configuración: se observó ghosting transitorio al desplazar la vista (~8 s), duplicando visualmente RAM/SSD durante algunos frames.
- Historial: con 83 sesiones, la primera apertura tardó varios segundos y construyó una lista demasiado extensa.
- Evidencia: el campo readonly de ruta JSON tenía un fondo visualmente ajeno a la paleta CorePulse.

## Correcciones V191

- Configuración compactada y ayuda redundante no construida.
- Historial: 12 tarjetas iniciales + 12 bajo demanda.
- Ruta JSON con `BENCH_SURFACE_SOFT` y `TEXT2`.
- Evidencia térmica CPU/GPU separada y legible.

## Integridad del benchmark

SHA-256 preservados respecto de V190:
- `core/directx_scene.py`: `879f7a664d2616fa5485477e9475393bf11bd5b2d082cfaf2bf934ac5c05f5ee`
- `core/benchmark_engine.py`: `c77426c5b56632cda58c13af0a032470656ef3ae55e81ac209a8ea4d5fb40fe5`
- `core/directx_benchmark.py`: `648c2caec5f6e4b3abf52dc1c3b16c93f67e7127a909be76d46113b6d1aa64a0`
- HLSL V16: `c0367450991a682dd9ece98c7a3d1c5b5062fbafb7f37a51c3ce197a632b5b9f`

## Pruebas

- `tests/test_v191_benchmark_v16_ux_refinement.py`: 6/6 PASS.
- Seguridad térmica y cierre V179/V180/V181 + contratos V190 actuales: 26 PASS.
- Contratos de método/timing V16 V184 relevantes: 5 PASS; el único guard no usado exige literalmente el antiguo texto de la etiqueta térmica y queda obsoleto por el rediseño V191.
- `py_compile`/`compileall`: PASS.

No se afirma validación visual de V191 en Windows hasta ejecutar la versión y revisar una nueva grabación.
