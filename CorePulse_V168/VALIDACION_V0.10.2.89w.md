# Validación CorePulse V0.10.2.89w

## Alcance
Liberación profunda de RAM con mecanismos de Windows comparables en alcance a un limpiador de memoria dedicado, preservando medición real y sin objetivo artificial de porcentaje.

## Cambios validados
- Working sets de procesos mediante `EmptyWorkingSet`.
- Working sets globales mediante `SystemMemoryListInformation / MemoryEmptyWorkingSets`.
- Lista modificada mediante `MemoryFlushModifiedList`.
- File-system cache mediante `SetSystemFileCacheSize(-1, -1, 0)`.
- Standby de baja prioridad y standby completa mediante `SystemMemoryListInformation`.
- Cada región es best-effort y conserva trazabilidad de éxito/fallo.
- `target_percent=None`: no se inventa ni promete 99%.
- Game Boost conserva la ruta independiente `GAME_STANDBY_PURGE_ONLY`.

## Validación en contenedor
- `python -m compileall -q .`: PASS.
- `pytest tests/test_memreduct_style_deep_ram_reclaim.py`: 3/3 PASS.
- 18 suites script de regresión seleccionadas: PASS.
- Regresiones cubiertas: Game Boost, Safe Storage Scanner, Windows, persistencia de energía, navegación de detalles, Centro de Salud, Gaming, CPU/RAM/GPU, EXE, rollback e instalador.

## Limitación de validación
El contenedor de validación no es Windows. Las llamadas reales a `NtSetSystemInformation`, `EmptyWorkingSet` y `SetSystemFileCacheSize` requieren validación de ejecución en Windows 10/11 con privilegios de administrador. CorePulse degrada cada capacidad de forma independiente si Windows la rechaza.
