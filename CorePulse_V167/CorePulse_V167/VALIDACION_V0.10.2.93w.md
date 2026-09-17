# Validación CorePulse V0.10.2.93w

## Objetivo
Restaurar la experiencia de arranque en un PC nuevo sin exigir al usuario ejecutar manualmente `instalar_dependencias.bat` ni copiar un `.venv` del equipo anterior.

## Garantías estructurales
- `Iniciar_CorePulse.bat` -> `CorePulse.vbs` -> `CorePulse_Bootstrap.bat` -> `bootstrap_corepulse.py`.
- El bootstrap usa únicamente stdlib/Tkinter antes de preparar el runtime.
- Se crea/repara `.venv` local con Python 3.12 x64.
- Runtime separado en `requirements-runtime-lock.txt`.
- Matplotlib y platformdirs forman parte del lock runtime.
- Se validan imports reales y DLL de LibreHardwareMonitor/HidSharp.
- `main.py` y `corepulse_launcher.py` se autocorrigen si se ejecutan desde un Python ajeno al `.venv` local.
- El EXE/frozen conserva su ruta y self-test existentes; no usa el bootstrap fuente.

## Limitación de validación en este entorno
La creación real de un `.venv` Windows y la instalación de wheels Win32/Win64 deben validarse en Windows. La regresión de este paquete valida estructura, sintaxis y políticas, pero no finge haber ejecutado el bootstrap nativo Windows desde Linux.

## Resultado en entorno de validación
- `compileall`: PASS.
- `test_self_bootstrapping_runtime_restore.py`: 17/17 PASS.
- Distribución/installer: PASS.
- EXE runtime integrity estructural: PASS.
- Startup responsiveness: 21/21 PASS.
- First telemetry gate: 11/11 PASS.
- Frozen dependency preflight: PASS.
- 20 suites críticas adicionales (batería, Windows, Gaming, energía, Game Boost, storage, tweaks, CPU/GPU, navegación/hover): 20/20 PASS.
- Helper probe: versión `0.10.2.93w` confirmada.

La ejecución nativa de creación/reparación de `.venv` y descarga de wheels Windows queda para validación en Windows; no se declara como ejecutada desde Linux.
