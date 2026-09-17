# Validación V0.10.2.86w — Persistent Windows Power Profiles

## Contrato funcional
- Un perfil manual exitoso queda activo en Windows al cerrar CorePulse.
- Reiniciar CorePulse detecta y refleja el plan real que Windows conserva.
- Cambiar el plan desde Windows es respetado; CorePulse no lo fuerza de vuelta.
- Un fallo durante la aplicación sí ejecuta rollback inmediato.
- Game Boost sigue siendo temporal y se desmonta al cerrar la sesión/aplicación.

## Validación automatizada
- `test_persistent_windows_power_profiles.py`: PASS.
- `test_performance_profiles.py`: PASS.
- `test_windows_power_plan_sync.py`: PASS.
- `test_game_boost_automation.py`: PASS.
- Regresión seleccionada de Gaming, Centro de Salud, startup, EXE, sensores, almacenamiento y Tweaks: 32/32 suites PASS.
- `compileall` completo: PASS.

## Alcance
No se modifican fuentes de telemetría, sensores, FPS ni políticas `REAL_OR_NA` / `REAL_FPS_OR_NA_ONLY`.
