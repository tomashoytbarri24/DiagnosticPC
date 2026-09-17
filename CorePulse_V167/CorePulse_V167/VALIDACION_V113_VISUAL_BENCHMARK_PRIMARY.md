# CorePulse V113 — Visual Benchmark Primary

## Evidencia revisada

La grabación real del MSI GE66 muestra la ventana `CorePulse Visual Benchmark 3D — Extendido`, renderizado visible continuo y resultado final con FPS/frametime y telemetría. El renderer reportado en la ejecución fue NVIDIA GeForce RTX 2070/PCIe/SSE2.

## Correcciones de robustez

- Warm-up separado de la ventana de medición.
- Resolución del perfil aplicada al área cliente real mediante `AdjustWindowRectEx` + `GetClientRect`.
- Ventana de benchmark fija para no alterar la carga accidentalmente por resize/maximizado.
- Estructura Win32 `MSG` completa (`lPrivate`).
- Validación de puntero de `wglGetProcAddress` antes de invocar `wglSwapIntervalEXT`.
- Registro de si VSync pudo desactivarse y calidad de medición asociada.
- 1% Low calculado desde el promedio del 1% de frametimes más lentos.
- Fallo de `SwapBuffers` tratado como ERROR real.
- Telemetría paralela ampliada con uso GPU, temperatura CPU/GPU y VRAM usada cuando existe.

## UI

El benchmark legacy de CPU/RAM/SSD/GPU fue retirado del runtime y de la interfaz Gaming. La vista Benchmark ahora expone únicamente el benchmark visual 3D.

## Política

`REAL_OR_NA` / `REAL_FPS_OR_NA_ONLY`: PASS.
