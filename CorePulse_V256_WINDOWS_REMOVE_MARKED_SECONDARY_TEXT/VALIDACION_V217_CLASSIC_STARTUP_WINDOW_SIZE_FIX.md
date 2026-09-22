# V217 — Windows Mainline · Classic Startup Window Size Fix

## Problema corregido
CorePulse seguía iniciando con una ventana demasiado grande aunque el estado fuera `normal`. La causa era el cálculo del preset Automático, que escalaba la ventana hasta aproximadamente 84-90% del área disponible y podía verse casi maximizada, especialmente con DPI de Windows.

## Cambios
- El tamaño preferido vuelve a **1280x800**.
- `Automático` ya no crece con el tamaño del monitor: parte de 1280x800 y sólo se reduce si la pantalla no alcanza.
- `Recomendado` pasa a 1280x800.
- Los presets antiguos de CorePulse en `Recomendado` se migran al nuevo tamaño clásico.
- Tras `deiconify`, la geometría se reafirma inmediatamente y una vez más a los 120 ms para evitar reajustes del Window Manager.
- Ocultar el sidebar no modifica el tamaño externo de la ventana; sólo redistribuye el contenido interior.

## Política
- No se modifica telemetría ni REAL_OR_NA.
