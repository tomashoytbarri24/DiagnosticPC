# VALIDACIÓN V300 — SIDEBAR RESPONSIVE FLOW FIX

## Base
- V299.

## Problema corregido
En PCs con ancho compacto o escalado DPI, `mode == compact` forzaba el bloque Personalización a `side=bottom`, aunque hubiera altura suficiente. Eso generaba un hueco grande entre Historial y Personalización.

## Solución
- Personalización siempre permanece en el flujo normal inmediatamente después de Historial.
- El modo compacto por ancho ya no determina el anclaje vertical.
- En alturas realmente bajas (<690 px) solo se reducen alturas/paddings.
- Se conserva íntegro el fix de frecuencia CPU de V299.

## Política
No se modifica ninguna fuente de telemetría ni REAL_OR_NA / REAL_FPS_OR_NA_ONLY.
