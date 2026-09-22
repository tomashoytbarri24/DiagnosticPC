# CorePulse V176 — persistencia del resultado GPU V12

Archivos modificados:

- `core/benchmark_engine.py`: guardado JSON atómico del último resultado GPU V12 y resolución portable de ruta.
- `gui/health_center_panel.py`: muestra la ruta absoluta al finalizar correctamente.
- `tools/probar_benchmark_gpu_v12.py` y `Probar_Benchmark_GPU_V12.bat`: la prueba manual usa la misma persistencia V176 y no reemplaza un resultado válido si falla o se cancela.
- `CHANGELOG.md`: registro de la versión.
- `tests/test_gpu_v12_result_persistence_v176.py`: prueba automatizada de creación, sobrescritura y REAL_OR_NA.

Ruta generada:

`resultados/benchmark_gpu_v12_ultimo_resultado.json`

La prueba no ejecuta ni simula el benchmark. Recibe un resultado controlado como entrada de la capa de persistencia y verifica que el JSON conserva las mediciones entregadas, representa datos no disponibles sin inventarlos, crea la carpeta y reemplaza el resultado anterior.

## Prueba realizada en Work

- Compilación de `core/benchmark_engine.py`, `gui/health_center_panel.py` y la prueba V176: **PASS**.
- Creación automática de `resultados/benchmark_gpu_v12_ultimo_resultado.json`: **PASS**.
- Segunda escritura sobre la misma ruta: **PASS** (`61.25` FPS fue reemplazado por `72.5` FPS).
- Métrica ausente `None` conservada como `null`: **PASS**.
- Valor no finito rechazado y guardado como `N/A`: **PASS**.
- Mensaje final con ruta absoluta: **PASS**.
- SHA-256 de `core/directx_benchmark.py` en V175 y V176: `e3041fd1831849b70087bd21d7ff3e2f88f31f253d0a009eec7c7556d0c17533` en ambos archivos.

La prueba funcional DirectX completa debe ejecutarse en Windows con una GPU D3D11; Work usa Linux y no inventa un resultado gráfico.
