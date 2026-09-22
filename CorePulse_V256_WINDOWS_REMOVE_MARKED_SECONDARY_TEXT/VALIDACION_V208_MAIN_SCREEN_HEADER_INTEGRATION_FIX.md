# V208 — Windows Mainline · Main Screen Header Integration Fix

## Objetivo
Corregir la percepción visual rara del header principal observada en la captura: bloque derecho partido, línea de actualización colgando y sensación de paneles flotantes.

## Cambios aplicados
- La cabecera vuelve a una altura más compacta.
- El panel derecho se integra en **una sola tarjeta**, sin subpanel inferior separado.
- El estado de monitoreo y la última actualización ahora viven en el mismo bloque visual.
- Se reduce el aspecto fragmentado del hero para que se lea como una sola pieza.

## Política
- Se mantiene **REAL_OR_NA**.
- No cambia la telemetría; sólo la presentación visual.
