# CorePulse — Base canónica V257

## Rama vigente

- Plataforma: Windows.
- Plataforma exclusiva: no se mantienen backends alternativos de sistema operativo.
- Aplicación: **V257**.
- Benchmark GPU vigente: **V25** (`core/benchmark_version.py`).
- Backend GPU: Direct3D 11 hardware.
- Política: **REAL_OR_NA** y **REAL_FPS_OR_NA_ONLY**.
- Si una métrica real no puede obtenerse o validarse, debe quedar en N/A.

## Arranque fuente

- `main.py` y `corepulse_launcher.py` usan directamente el intérprete seleccionado en el PC.
- `Iniciar_CorePulse.bat` -> `CorePulse.vbs` abre `corepulse_launcher.py`.
- No existe bootstrap automático de Python ni recreación automática de `.venv`.
- El EXE/instalador final debe ser autocontenido.

## Benchmark

- El benchmark principal usa `core/directx_benchmark.py` y `core/benchmark_engine.py`.
- Resultado persistente: `resultados/benchmark_gpu_v25_ultimo_resultado.json`.
- La carpeta `resultados` se crea automáticamente al guardar un resultado válido.
- `tools/presentmon/PresentMon.exe` se conserva para evidencia FPS/frametime real cuando corresponde.

## Limpieza V257

Se retiraron archivos históricos, cachés, runners versionados y módulos sin ruta de ejecución vigente. No se eliminaron módulos con referencias de runtime o imports dinámicos potenciales.
