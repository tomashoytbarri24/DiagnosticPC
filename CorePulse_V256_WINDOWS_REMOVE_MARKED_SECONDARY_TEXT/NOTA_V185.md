# CorePulse V185 — Benchmark GPU V16 UI Ghost Fix

V185 es un parche de interfaz sobre V184. El benchmark GPU sigue siendo V16.

## Alcance
- Corrige texto/restos fantasma de un frame anterior durante scroll con rueda en Windows.
- Mantiene el repaint limitado por frame; no usa `update()` reentrante.
- No modifica DirectX, escenas, shaders, geometría, tiempos, FPS, 1% Low, timestamps GPU, seguridad térmica ni persistencia del JSON V16.
