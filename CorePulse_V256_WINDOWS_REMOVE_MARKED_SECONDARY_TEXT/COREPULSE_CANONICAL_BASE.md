# Base canónica vigente — V200 Windows / Benchmark GPU V20

V200 deriva de V199 Windows. La rama Linux continúa fuera de esta línea principal.

## Base canónica actual
V199 Windows — Benchmark GPU V19 Knowledge Clarity.

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

## Benchmark canónico actual — V198 Windows / GPU V19

- El benchmark principal está en la página dedicada `Benchmark` y usa `core/directx_benchmark.py`.
- Backend vigente: **Direct3D 11 hardware**; no existe fallback silencioso que cambie la metodología.
- Benchmark GPU vigente: **V19**, identificado desde `core/benchmark_version.py`.
- Perfil estándar GPU: 5 s de warm-up global, settle/prime excluidos y **49 s medidos** distribuidos en Valle/Bosque/Lago/Extreme.
- FPS, 1% Low y frametimes proceden de frames realmente presentados; GPU time usa timestamp queries cuando el driver las valida.
- `REAL_OR_NA` y `REAL_FPS_OR_NA_ONLY` siguen vigentes: si algo no se mide de forma fiable, permanece N/A.
- Resultado GPU vigente: `resultados/benchmark_gpu_v19_ultimo_resultado.json`.
- V198 añade `Lectura CorePulse`: interpretación basada sólo en estado, integridad, estabilidad y temperatura realmente observados; no modifica el workload ni crea rankings externos.
- `core/visual_benchmark.py` se conserva sólo por compatibilidad histórica; no es el benchmark GPU principal de la rama Windows actual.
