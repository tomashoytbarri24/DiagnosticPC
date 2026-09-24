# Validación V317 — Health copy + visual tune

## Objetivo
Pulir el bloque visual de salud para que el copy sea menos técnico y el texto interno de las tarjetas tenga mayor contraste.

## Cambios aplicados
- Se cambió el texto interno relevante de las tarjetas del resumen desde gris/plomo a blanco para mejorar lectura.
- Se mantuvo el color de acento solo en encabezados/indicadores funcionales.
- Se reemplazó el copy técnico con `TjMax` por una redacción más amigable:
  - antes: `CPU a X °C de TjMax`
  - ahora: `Temperatura cerca del máximo valor permitido`
- Se mantuvo intacta la lógica real de cálculo del porcentaje de salud.

## Validación técnica
- `py_compile` OK en:
  - `gui/dashboard.py`
  - `gui/live_health_binding.py`
  - `main.py`
  - `core/live_health.py`

## Política preservada
- REAL_OR_NA intacto.
- Sin inventar sensores ni valores.
- Solo se ajustó presentación visual y copy de interfaz.
