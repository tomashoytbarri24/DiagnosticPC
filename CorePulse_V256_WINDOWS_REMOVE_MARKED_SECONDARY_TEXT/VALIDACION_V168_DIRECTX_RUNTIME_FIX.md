# CorePulse V168 — DirectX 11 Runtime Fix

## Problema reproducido desde V167

La ventana del benchmark podía quedar negra y finalizar con `OSError: exception: access violation`.
La causa era el uso de índices incorrectos de la vtable de `ID3D11DeviceContext` en varias llamadas críticas (IA, shaders, render targets, viewport, actualización de constant buffer y clears).

## Corrección V168

- Se centralizaron los slots de `ID3D11DeviceContext` según el orden de `d3d11.h`.
- Ya no existen números mágicos para las llamadas del DeviceContext en el renderer.
- La ventana DirectX se crea oculta y sólo se muestra después de un frame 3D completo presentado correctamente.
- El arranque valida por etapas: ventana, device/swapchain, clear/present, shaders, recursos y primer frame 3D.
- Los errores incluyen `failure_stage` y `startup_checks` en el JSON del benchmark.
- Se eliminó el corte fijo de benchmark en CPU >=96 °C. Cuando existe sensor de distancia a TjMax, se usa esa evidencia real y sostenida; 95–99 °C se registra como advertencia, no como aborto automático.
- El stress test usa la misma idea de margen térmico real/sostenido en vez de asumir que 96 °C es el TjMax universal.
- Las ejecuciones V168 tienen nuevos IDs de metodología para no mezclarse con resultados V167 defectuosos.

## Validación disponible en entorno de build

- `python -m compileall`: PASS.
- Tests DirectX V168 + adaptación V167: 13/13 PASS.
- Smoke CPU/RAM del motor de benchmark: PASS.
- `compileall`: PASS.
- Validación física de Direct3D 11: pendiente necesariamente de PC Windows con GPU real.

## Prueba física recomendada

Ejecutar `Probar_Benchmark_GPU_V6_FIX.bat`. El test usa perfil rápido y guarda `benchmark_gpu_v6_ultimo_resultado.json`.
