# V216 — Windowed Startup Geometry Fix

## Problema corregido
Después de V215, CorePulse podía aparecer al inicio con tamaño tipo pantalla completa, aunque el comportamiento esperado era conservar la ventana normal centrada de versiones anteriores.

## Causa
La geometría preferida se aplicaba mientras el Startup Gate seguía activo. Al revelar la raíz, Windows podía conservar/publicar un estado o tamaño mayor al esperado.

## Solución
- `apply_preferred_launch_geometry()` acepta ahora `force=True`.
- Al cerrar el Startup Gate se fuerza primero:
  - `fullscreen = False`
  - `state('normal')`
  - reaplicación de la geometría preferida/guardada
  - centrado de la ventana
- Después de eso se hace `deiconify()`.
- El sidebar sigue ocultándose completamente y el Resumen se expande dentro de la ventana actual.

## No cambia
- REAL_OR_NA
- telemetría
- benchmark
- tamaño elegido por el usuario en preferencias
