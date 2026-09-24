# VALIDACIÓN V297 — MULTI-PYTHON RUNTIME

## Objetivo
Eliminar la dependencia de Python 3.12 exacto en modo fuente sin degradar funciones.

## Política
- CPython 3.12+ x64.
- Sin límite superior artificial por minor.
- Una versión sólo se declara compatible si instala y carga el stack completo.
- Si `pythonnet`, `pywin32`, HardwareMonitor o LibreHardwareMonitor fallan, el instalador devuelve error; no se oculta la pérdida de funcionalidad.

## Flujo
1. Detecta el Python disponible o acepta una ruta explícita.
2. Crea un venv aislado por minor.
3. Intenta el lock exacto.
4. Si el lock exacto no tiene wheels para ese minor, prueba constraints flexibles.
5. Ejecuta `tools/validate_python_runtime.py`.
6. Registra el runtime validado en `.corepulse_runtime_python.txt`.
7. `main.py` / `corepulse_launcher.py` pueden reejecutarse automáticamente allí si fueron lanzados desde otro Python sin dependencias.

## Ejemplo Python 3.14
`instalar_dependencias.bat C:\Python314\python.exe`

Luego cualquiera de estos comandos puede iniciar CorePulse:
- `C:\Python314\python.exe corepulse_launcher.py`
- `python corepulse_launcher.py`
- `python main.py`

Si el Python invocado no tiene dependencias, el bootstrap usa el runtime validado.
