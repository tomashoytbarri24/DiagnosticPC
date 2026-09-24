# VALIDACIÓN V303 — SIDEBAR MICRO TRANSITION

## Base
- V302

## Cambio
- Se elimina la cortina visual de pantalla completa.
- Sólo se muestra un velo de 22 px junto al borde del contenido.
- El velo se contrae en ~64 ms tras el reflow.
- El dashboard nunca desaparece durante la transición.

## Integridad
- No altera telemetría, sensores, REAL_OR_NA ni REAL_FPS_OR_NA_ONLY.
