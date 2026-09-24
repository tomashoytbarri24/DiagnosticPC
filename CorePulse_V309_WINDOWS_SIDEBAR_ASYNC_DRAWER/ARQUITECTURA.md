# Arquitectura actual de CorePulse V257

## Entrada
- `main.py`: aplicación principal.
- `corepulse_launcher.py`: launcher fuente.
- `Iniciar_CorePulse.bat` + `CorePulse.vbs`: acceso rápido en Windows.

## Capas
- `core/`: telemetría, diagnóstico, benchmark, almacenamiento, FPS, IA, mantenimiento y políticas de integridad.
- `gui/`: dashboard y paneles de interfaz.
- `performance/`: Game Boost, perfiles y energía.
- `database/`: persistencia de telemetría/historial.
- `assets/`: iconos y recursos visuales.
- `tools/presentmon/`: binario requerido para captura PresentMon.
- `build/` + `installer/`: empaquetado PyInstaller e instalador.

## Contratos
- `REAL_OR_NA`: ninguna métrica ausente se reemplaza por datos inventados.
- `REAL_FPS_OR_NA_ONLY`: FPS sólo de fuentes reales/medidas.
- SMART, temperaturas, salud y benchmark conservan fuente y trazabilidad.
- El benchmark GPU vigente es V25 y su identidad está centralizada en `core/benchmark_version.py`.

## Directorios generados
`logs/`, `resultados/`, cachés de Python y otros artefactos de ejecución no forman parte del código fuente limpio; se crean en runtime cuando corresponde.
