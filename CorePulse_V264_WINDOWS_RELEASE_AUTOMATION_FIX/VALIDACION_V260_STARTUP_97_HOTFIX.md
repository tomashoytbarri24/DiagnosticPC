# Validación V260 — Startup 97% Hotfix

## Causa
V259 eliminó visualmente la tarjeta «Estado del agente», incluyendo su etiqueta de última actualización, pero `_wrap_telemetry_update()` aún accedía a `self._header_last_update`. La primera muestra real sí se procesaba en el renderer base, pero el wrapper lanzaba `AttributeError` después. `process_pending_telemetry()` no alcanzaba entonces `_complete_startup_after_first_telemetry()`, dejando `services=0.90`. Con el resto de componentes listos, el progreso resultante era aproximadamente 97 %.

## Corrección
- Se declara `app._header_last_update = None` al construir el header sin tarjeta de agente.
- El wrapper usa `getattr(..., None)` para que la actualización sea segura incluso si esa etiqueta no existe.
- No se altera la fuente ni el contenido de la telemetría.

## Alcance
Hotfix mínimo sobre V259; benchmark, Driver Hub y módulos restantes permanecen intactos salvo metadatos de versión/documentación.
