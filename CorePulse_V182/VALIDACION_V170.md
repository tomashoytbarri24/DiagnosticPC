# Validación CorePulse V170

## Objetivo

Mejorar la audibilidad del Test de Audio sin modificar el volumen maestro de Windows ni alterar otros módulos.

## Cambio

- El tono de prueba generado localmente por WASAPI pasa de amplitud pico `0.08` a `0.32`.
- Se mantiene la envolvente de 20 ms, duración y frecuencia existentes.
- No se invoca ninguna API de volumen del sistema ni del mezclador de Windows.
- Los canales izquierdo/derecho continúan aislados por muestras reales; `Ambos` reproduce en L/R.

## Validación automatizada

- Pruebas nativas de aislamiento y nivel de muestra actualizadas al nuevo margen.
- Quality Gate completo debe permanecer en PASS.

## Windows real pendiente

Validar perceptualmente en altavoces/auriculares reales que L/R/Ambos se escuchen con un nivel cómodo y sin distorsión.
