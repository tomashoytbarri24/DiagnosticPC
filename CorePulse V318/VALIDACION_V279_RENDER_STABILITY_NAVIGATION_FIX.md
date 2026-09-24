# VALIDACIÓN V279 — RENDER STABILITY + NAVIGATION FIX

## Base
- V277. La V278 queda descartada y no forma parte de esta rama.

## Fallos atacados
1. Parpadeo/tearing al mover el mouse por el sidebar con la X hover.
2. Frames negros o vacíos al entrar por primera vez a Benchmark.

## Sidebar
- La X permanece geométricamente mapeada arriba a la derecha.
- Se oculta mostrando texto vacío, no con `place_forget()`.
- Se eliminó el bind recursivo sobre cada widget hijo.
- Se usa un debounce de 90 ms y comprobación geométrica del puntero al salir.

## Benchmark
- Se agregó `stage_internal_page()` para pre-mapear el host detrás de la vista actual.
- Benchmark hace el commit final 16 ms después de la fase de staging.
- El panel pesado se construye en un staging host fuera del viewport.
- El loading se conserva hasta que el contenido pesado ya resolvió geometría.

## Contratos preservados
- REAL_OR_NA
- REAL_FPS_OR_NA_ONLY
- Sin cambios en telemetría, sensores, SMART o lógica del benchmark.
