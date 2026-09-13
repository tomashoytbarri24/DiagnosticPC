# Validación V0.10.2.95w — Bootstrap Pip Resilience Fix

## Problema reproducido

En un PC nuevo, el bootstrap V0.10.2.94w detenía toda la preparación si fallaba el paso previo:

`python -m pip install --upgrade pip setuptools wheel`

Ese upgrade no forma parte del runtime funcional de CorePulse y no debe ser una condición de arranque.

## Corrección

- El `.venv` comprueba primero `python -m pip --version`.
- Si pip no existe o está roto, se intenta `python -m ensurepip --upgrade`, sin depender de PyPI.
- No se ejecuta ningún upgrade obligatorio de pip/setuptools/wheel antes de instalar CorePulse.
- Se instala directamente `requirements-runtime-lock.txt` con `--prefer-binary`, reintentos y timeout explícito.
- Si la instalación real falla, el usuario recibe el detalle final de pip y `runtime_bootstrap.log` conserva el registro completo.
- Se conserva el reconocimiento de `python.exe` y `pythonw.exe` del `.venv`, evitando el loop corregido en 94w.

## Validación estructural

- `compileall`: PASS.
- `test_bootstrap_pip_resilience_fix.py`: PASS (8/8).
- `test_bootstrap_relaunch_loop_fix.py`: PASS (6/6).
- `test_self_bootstrapping_runtime_restore.py`: PASS.
- Startup gate, first telemetry, EXE/runtime integrity, launcher/installer: PASS.
- Batería, Windows, Gaming, perfiles persistentes, almacenamiento seguro, CPU/GPU y rollback: PASS en las suites seleccionadas.

## Límite del entorno de validación

El entorno de construcción actual no es Windows; por tanto, la descarga/instalación real de wheels Win64 debe validarse en un PC Windows. El flujo de bootstrap y sus decisiones de error sí fueron validados estructuralmente.
