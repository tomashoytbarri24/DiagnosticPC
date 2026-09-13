# CorePulse — Base canónica de arranque directo

Desde V113, el proyecto fuente ya no crea, repara ni valida automáticamente un entorno Python al iniciar.

## Contrato de arranque fuente

- `main.py` y `corepulse_launcher.py` arrancan directamente con el intérprete seleccionado en ese PC.
- `Iniciar_CorePulse.bat` -> `CorePulse.vbs` abre `corepulse_launcher.py` sin ejecutar un preparador de entorno.
- Si ya existe `.venv\Scripts\pythonw.exe`, puede reutilizarse.
- Si ya existe un runtime previo bajo `%USERPROFILE%\.corepulse\runtime`, puede reutilizarse, pero CorePulse no lo crea ni lo repara al arrancar.
- VS Code no impone una ruta de Python perteneciente a otro computador; cada desarrollador selecciona su propio intérprete.
- El instalador/EXE final deberá ser autocontenido y no depender de Python instalado por el usuario.

## Regla para versiones futuras

No volver a insertar `bootstrap_corepulse.py`, `core/source_runtime_bootstrap.py`, `core/runtime_venv_path.py` ni `CorePulse_Bootstrap.bat` en la cadena automática de inicio. El arranque fuente debe permanecer directo salvo una decisión explícita del proyecto.
