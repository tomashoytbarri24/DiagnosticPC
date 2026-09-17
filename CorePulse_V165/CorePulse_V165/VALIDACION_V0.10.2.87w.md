# Validación V0.10.2.87w — Power Profile Shutdown Persistence Fix

## Regresión reproducida
- Escenario simulado: plan original `HIGH_PERFORMANCE` → usuario selecciona `MAXIMUM_PERFORMANCE` → un teardown temporal cambia el plan de vuelta a `HIGH_PERFORMANCE`.
- Resultado esperado: el cierre reafirma el GUID exacto de `MAXIMUM_PERFORMANCE`.
- Nueva instancia: lee `MAXIMUM_PERFORMANCE`, no `BALANCED`.

## Contrato
- Un plan manual confirmado sobrevive al cierre de CorePulse.
- Game Boost termina antes de la verificación persistente.
- La última operación de energía de `main.on_close()` ocurre después de detener telemetría y sensores.
- Cambios manuales hechos desde Windows mientras CorePulse está abierto siguen siendo respetados.
- Si el cambio inicial falla, se conserva rollback inmediato.
- La UI no muestra Equilibrado sin evidencia durante la carga del gestor.

## Validación automatizada
- `test_power_profile_shutdown_persistence_fix.py`: PASS.
- Regresión seleccionada: 32/32 suites PASS.
- `compileall` completo: PASS.

## Limitación de entorno
La ejecución real de `powercfg` y el comportamiento post-cierre del equipo deben verificarse en Windows. Las pruebas automatizadas reproducen específicamente la regresión de un rollback temporal que cambia el plan durante shutdown.
