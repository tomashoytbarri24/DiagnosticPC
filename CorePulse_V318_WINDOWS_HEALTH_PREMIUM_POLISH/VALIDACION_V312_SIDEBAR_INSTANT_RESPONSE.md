# VALIDACIÓN V312 — SIDEBAR INSTANT RESPONSE

## Base
- CorePulse V311.

## Objetivo
- Conservar la estabilidad visual de V311 y reducir la sensación de lag al pulsar abrir/cerrar sidebar.

## Cambios
- Slide: 52 ms / 4 pasos.
- Se mantiene ease-out y commit nativo estabilizado.
- Se eliminan limpiezas heredadas de máscara/capas de la ruta crítica del clic.
- Reflow de gráficos: asíncrono tras el frame estable.

## Política de datos
- Sin cambios en telemetría.
- REAL_OR_NA y REAL_FPS_OR_NA_ONLY intactos.
