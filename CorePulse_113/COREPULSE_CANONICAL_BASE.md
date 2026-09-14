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

## Benchmark canónico desde V113

- El benchmark visible de Gaming es `Benchmark visual 3D` (`core/visual_benchmark.py`).
- La prueba genera carga OpenGL visible real y mide FPS/frametimes del bucle de presentación; no estima FPS.
- `REAL_OR_NA` y `REAL_FPS_OR_NA_ONLY` siguen vigentes: sensores ausentes permanecen en N/A.
- Los perfiles Rápido / Estándar / Extendido usan resolución, geometría, duración medida y warm-up definidos y reproducibles.
- El benchmark legacy por componentes CPU/RAM/SSD/GPU ya no se importa ni se publica en la interfaz Gaming. No volver a reinsertarlo como benchmark principal salvo decisión explícita del proyecto.
- CorePulse registra el renderer OpenGL real y el estado de VSync para que el resultado sea trazable.
