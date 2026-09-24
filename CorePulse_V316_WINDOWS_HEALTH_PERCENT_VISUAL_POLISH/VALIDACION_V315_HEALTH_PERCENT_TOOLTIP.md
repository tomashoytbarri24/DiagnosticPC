# Validación V315 — Health percent + tooltip

## Cambios aplicados
- La tarjeta **Salud del sistema** del resumen ahora muestra un **porcentaje real de salud**.
- El porcentaje reacciona a:
  - temperatura de CPU
  - temperatura de GPU
  - presión de RAM
  - porcentaje de uso del almacenamiento
  - salud SMART del almacenamiento
- El estado asociado ahora se expresa como:
  - ÓPTIMO
  - BUEN ESTADO
  - ESTADO MEDIO
  - REQUIERE REVISIÓN
  - CRÍTICO
- Cuando la salud baja, la tarjeta usa un **signo de advertencia**.
- Al poner el mouse sobre la tarjeta, aparece un **tooltip** con los factores que explican el porcentaje.

## Validación técnica
- `py_compile` OK en:
  - `core/health_engine.py`
  - `core/telemetry_reliable.py`
  - `gui/dashboard.py`
  - `gui/live_health_binding.py`
  - `main.py`

## Política preservada
- No se inventan sensores.
- Si falta evidencia suficiente, se mantiene `N/A / NO EVALUABLE`.
- Se preserva `REAL_OR_NA`.
