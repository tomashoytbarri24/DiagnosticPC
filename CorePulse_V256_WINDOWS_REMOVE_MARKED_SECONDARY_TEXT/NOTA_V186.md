# CorePulse V186 — Benchmark GPU V16 · Scroll Backend Fix

V186 corrige el ghosting persistente observado en V184/V185 al desplazar los resultados del benchmark en Windows.

## Causa aislada
La vista de resultados era un árbol CTk embebido mediante `Canvas.create_window`. Windows podía desplazar el Canvas y pintar algunos widgets hijos en frames distintos, dejando restos temporales del frame anterior. Forzar `RedrawWindow` reducía el efecto, pero no eliminaba la causa.

## Cambio
Sólo la página independiente de Benchmark utiliza ahora `StableScrollHost(backend="place")`. El contenido vive dentro de un viewport normal y se desplaza moviendo un único frame hijo, que queda recortado por su padre. No existe `Canvas.create_window` en ese backend.

## Alcance
No se modifican DirectX, escenas V16, shaders, geometría, tiempos, FPS, 1% Low, timestamps GPU, telemetría ni seguridad térmica.
