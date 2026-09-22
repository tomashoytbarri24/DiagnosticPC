# V178 — V13, candidata para validación en Windows

## Cambios
- `core/directx_benchmark.py`: materiales de agua, costa, terreno, hojas y avión; variación determinista de árboles y normales para escala no uniforme. Identificadores V13.
- `core/directx_scene.py`: estabilizadores y quilla hacia la cola -X, canopy hacia nariz +X.
- `core/benchmark_engine.py`: método V13 y persistencia independiente en `resultados/benchmark_gpu_v13_ultimo_resultado.json`.
- `core/benchmark_presentation.py`, `gui/health_center_panel.py`: etiquetas V13. Se mantienen las mejoras de interfaz V177.
- Lanzadores GPU V11/V12/V13: ejecutan el motor V13 de esta carpeta, identificado como tal. V12 original sigue en el proyecto V177 separado.
- Versión, README, CHANGELOG, VERSIONING y prueba `tests/test_v178_benchmark_v13.py`.

## Qué se conserva
49 segundos medidos (10/12/12/15), warm-up/settle/prime, reloj de pared, fórmula FPS/1% Low, timestamp GPU, consultas fuera de frametime, telemetría y REAL_OR_NA. Ningún resultado de rendimiento viene precargado.

Los efectos gráficos son contenido del workload, no telemetría simulada. V13 cambia el trabajo GPU y sus FPS no son directamente comparables con V12. El historial distingue los identificadores de método.

## Verificación
`python -m unittest tests.test_v177_benchmark_ui tests.test_v178_benchmark_v13 -v`

Se validan callbacks finales, persistencia visual, geometría finita/determinista, índices válidos, cola/cabina, contrato temporal y JSON independiente de V12. Se compilan módulos Python. El entorno Linux no dispone de Direct3D ni compilador HLSL: no se ha certificado compilación shader, aspecto, fluidez ni rendimiento en GPU real.

Resultado de esta entrega: 7/7 pruebas PASS, compilación Python PASS. Comparación AST de `run_directx_benchmark` contra V177: idéntica salvo sustitución de identificadores V12 por V13.

## Prueba en Windows
Extraer en carpeta nueva, conservar V177 e iniciar `Iniciar_CorePulse.bat`. Seleccionar GPU y completar el benchmark. Revisar agua, hojas y aviones; enviar video y `resultados/benchmark_gpu_v13_ultimo_resultado.json`. Si falla el shader, enviar el mensaje exacto de error. No usar resultados de V12 para rellenar V13.
