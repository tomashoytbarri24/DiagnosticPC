# Validación V316 — Health percent visual polish

## Objetivo
Pulir visualmente la tarjeta **Salud del sistema** del resumen sin perder el comportamiento funcional agregado en V315.

## Cambios aplicados
- Tarjeta de salud convertida a una versión visual dedicada:
  - porcentaje principal más grande
  - estado en *pill* visual (`ÓPTIMO`, `BUEN ESTADO`, `ESTADO MEDIO`, etc.)
  - barra de progreso del porcentaje
  - resumen corto inferior
  - hint inferior para hover
- Tooltip rediseñado:
  - borde con color de severidad
  - layout oscuro consistente con CorePulse
  - título + cuerpo más limpio
  - mensajes más breves y legibles
- La lógica funcional sigue reaccionando a:
  - temperatura CPU/GPU
  - presión de RAM
  - espacio ocupado del almacenamiento
  - salud SMART del almacenamiento

## Validación técnica
- `py_compile` OK en:
  - `gui/dashboard.py`
  - `gui/live_health_binding.py`
  - `core/health_engine.py`
  - `core/telemetry_reliable.py`
  - `main.py`

## Política preservada
- REAL_OR_NA intacto.
- Sin sensores inventados.
- Si no hay evidencia suficiente, sigue correspondiendo `N/A / NO EVALUABLE`.
