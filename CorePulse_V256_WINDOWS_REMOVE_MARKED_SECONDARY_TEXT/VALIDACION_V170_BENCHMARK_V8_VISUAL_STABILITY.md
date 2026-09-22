# CorePulse V170 — Validación Benchmark V8 Visual Stability

## Objetivo

Corregir el artefacto visual observado en V169 (polígono azul grande que aparecía al avanzar la cámara), mejorar la lectura de jets/nubes/agua y conservar la medición GPU real por timestamp queries de Direct3D 11.

## Cambios verificables

- El sky mesh dejó de reutilizar la geometría irregular de `build_rock`.
- `build_sky()` crea una esfera UV de radio unitario, sin *wobble*.
- En el vertex shader el cielo se traslada a `CameraTime.xyz` cada frame y queda a 680 unidades de la cámara.
- El pixel shader calcula la dirección del cielo con `i.world - CameraTime.xyz`.
- Las nubes son clusters de cinco lóbulos 3D; su movimiento es determinista y depende sólo del tiempo de la escena y `SV_InstanceID`.
- El jet procedural incorpora fuselaje, ala delta, estabilizadores, quilla y canopy identificado por atributo UV.
- El agua usa tres ondas deterministas y especular solar.
- El método GPU pasa a `COREPULSE_GPU_DIRECTX11_SCENES_V8`; los resultados V7 no se mezclan con V8.

## Timing estándar

La duración deliberada no cambia:

- Low: 2,0 s warm-up + 8,0 s medidos.
- Medium: 2,0 s warm-up + 8,0 s medidos.
- High: 2,5 s warm-up + 8,0 s medidos.
- Extreme: 3,0 s warm-up + 8,0 s medidos.
- Total objetivo: 41,5 s, más overhead mínimo de inicialización/cierre.

## Workload derivado del mesh V8

Los conteos se calculan desde las mallas realmente creadas. Con los parámetros V8:

- Low: ~57.536 triángulos/frame.
- Medium: ~118.488 triángulos/frame.
- High: ~241.748 triángulos/frame.
- Extreme: ~466.572 triángulos/frame.

Estos números no son un score: describen sólo el workload geométrico aproximado. Shader iterations y texture samples también aumentan por nivel.

## Validación ejecutada en el entorno de construcción

- `tests/test_v170_benchmark_v8_visual_stability.py`: 7/7 PASS.
- Smoke tests DirectX V168/V169 que no fijan IDs históricos: 12/12 PASS.
- Compilación Python: 401 archivos, 0 errores.
- Integridad de índices de sky/cloud/jet: PASS.
- Progresión estricta Low < Medium < High < Extreme: PASS.

## Límite de esta validación

El entorno de construcción no dispone de Direct3D 11 de Windows, por lo que no puede certificar el frame final renderizado por un driver real. La validación física debe hacerse en Windows con `Probar_Benchmark_GPU_V8.bat`. El resultado queda en `benchmark_gpu_v8_ultimo_resultado.json`.

La aceptación de V170 requiere comprobar en Windows que:

1. no reaparece ninguna faceta/polígono gigante del sky dome;
2. las cuatro escenas completan su tiempo objetivo;
3. `gpu_timestamp_coverage` contiene muestras reales o queda N/A si el driver no las entrega;
4. Low/Medium/High/Extreme muestran la progresión esperada del workload sin crash ni ventana negra.
