# CorePulse V141 — Centro de salud compacto y optimización UI

## Objetivo
Reducir densidad visual y trabajo de interfaz del Centro de salud sin alterar autoridades de telemetría ni SMART/NVMe.

## Cambios
- El resumen general usa una tarjeta compacta con tipografía mayor y evidencia visible.
- Se elimina de la portada el índice porcentual poco contextual y los textos repetidos de política.
- `Conviene vigilar` pasa a `Seguimiento recomendado` cuando existe evidencia de nivel ATTENTION.
- La tarjeta pública `CorePulse` se retira del Centro de salud; el backend de autodiagnóstico se conserva para usos técnicos futuros.
- Las tarjetas de módulos eliminan pills y cajas de estado redundantes, reduciendo widgets y altura.
- El autodiagnóstico técnico se importa de forma lazy sólo si se invoca explícitamente.

## Contratos preservados
- REAL_OR_NA.
- Runtime universal canónico.
- NVMe/SMART canónico.
- Batería sólo aparece cuando su presencia fue confirmada.
