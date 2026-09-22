# Validación V259 — Benchmark & Driver Hub

## Objetivo

Corregir exclusivamente los problemas observados en la prueba real de V258: tarjeta redundante del agente, espacio previo al benchmark, drag del scroll posterior y exceso de ruido/acciones individuales en controladores.

## Comprobaciones estáticas

- V259 centralizada en `core/version.py`, `LATEST_VERSION.txt` y `pyproject.toml`.
- Benchmark GPU conserva identidad V25.
- El bloque Estado de la prueba no se renderiza antes de iniciar.
- Las páginas estáticas de resultado usan `StableScrollHost(... backend='canvas')`.
- Dashboard no crea la tarjeta visual Estado del agente.
- Driver Hub contiene Descargar todo / Instalar todo y deja firmware fuera de instalación masiva.
- Inventario técnico queda oculto por defecto.
- Gestión de drivers no usa el COM de Windows Update Agent.
- Búsqueda de paquetes se hace por ID de hardware y la instalación final pasa por PnPUtil.

La validación real de detección/descarga/instalación de controladores requiere Windows y hardware físico; fuera de Windows sólo se validan parser, flujo y contratos de seguridad.

## Resultado de validación en entorno de construcción

- 149 archivos Python compilados: **0 errores**.
- `pytest`: **6/6 pruebas aprobadas**.
- Parser del catálogo probado con HTML sintético: GUID, versión y tamaño extraídos correctamente.
- Selección de dispositivos probada con saturación de GPU/System: conserva cupos para firmware y software components.
- Hashes del motor Benchmark V25 (`benchmark_engine.py`, `directx_benchmark.py`, `directx_scene.py`, `benchmark_version.py`) idénticos a V258.
