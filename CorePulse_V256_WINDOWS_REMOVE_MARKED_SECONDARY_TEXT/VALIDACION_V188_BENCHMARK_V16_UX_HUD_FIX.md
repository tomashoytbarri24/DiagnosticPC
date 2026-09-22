# Validación V188 — Benchmark GPU V16 UX/HUD Fix

## Alcance

V188 modifica la experiencia de Benchmark, no el workload GPU. Se preservan DirectX 11 V16, escenas, shaders, wall-clock, timestamps GPU, seguridad térmica y persistencia REAL_OR_NA.

## Cambios auditados

- HUD externo al swap-chain con escena + FPS real obtenido del callback de progreso.
- Durante warm-up/settle, FPS se publica como N/A.
- Cursor oculto durante fase GPU y restaurado con el mismo número de llamadas a `ShowCursor`.
- Configuración y bloque Ejecutar ocultos una vez finalizada la prueba.
- Acciones compactas: Repetir prueba / Cambiar componentes.
- Resumen autoexplicativo por carga.
- Compatibilidad de sensores bajo demanda.
- Cambio de pestaña de resultados vuelve al inicio del viewport.

## Integridad del workload V16

Los siguientes archivos son byte por byte idénticos a V187:

- `core/directx_benchmark.py`
- `core/directx_scene.py`
- `core/benchmark_engine.py`

Por lo tanto V188 conserva el identificador y archivo de resultado `benchmark_gpu_v16_ultimo_resultado.json`.

## Pruebas

- `py_compile`: PASS.
- V188 UX/HUD: 5/5 PASS.
- Regresiones térmicas/UI/Benchmark V16 vigentes: 37 PASS.
- Se excluyen únicamente guards históricos que exigen literalmente V13/V180 o números de versión anteriores.

## Limitación de esta validación

Este entorno no renderiza el benchmark Direct3D de Windows ni puede confirmar visualmente que las ventanas topmost del HUD queden por encima del swap-chain en el equipo final. Esa comprobación debe hacerse con una ejecución real en Windows y video. No se simula ni se afirma una ejecución DirectX inexistente.
