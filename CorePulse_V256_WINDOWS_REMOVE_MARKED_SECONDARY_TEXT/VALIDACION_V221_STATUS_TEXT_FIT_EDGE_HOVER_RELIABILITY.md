# V221 — Status Text Fit + Edge Hover Reliability

## Objetivo
Corregir dos fallas observadas en V220: texto recortado en las tarjetas superiores y cascada/flecha que desaparecía al intentar alcanzarla.

## Cambios
- Salud del sistema y Supervisión actual ganan ancho relativo.
- Valores largos usan tipografía y wrap adaptativos en compact/standard/large.
- El alto del status band aumenta levemente para permitir dos líneas sin recorte.
- El handler de Leave deja de estar ligado globalmente a todos los widgets.
- Antes de ocultar la cascada se verifica que el cursor haya salido realmente de la ventana.
- La zona de hover del borde se amplía y el delay de ocultado aumenta.

## Política
- REAL_OR_NA intacto.
- Sin cambios en telemetría o diagnóstico.
