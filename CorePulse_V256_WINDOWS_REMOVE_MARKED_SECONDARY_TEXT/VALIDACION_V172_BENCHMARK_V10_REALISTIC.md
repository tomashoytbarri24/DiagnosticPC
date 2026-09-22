# Validación V172 — Benchmark GPU V10 · Realistic Materials + Isolated Frametime

## Objetivo

V172 parte de la V171 funcional. No cambia el backend Direct3D 11 por otro renderer: corrige la metodología temporal del benchmark y mejora la escena sin introducir valores sintéticos ni lookup por modelo.

## Metodología estándar

- API: Direct3D 11 hardware.
- Resolución objetivo: 1920×1080.
- VSync: OFF.
- Escenas: Valle, Bosque, Lago, Extreme.
- Medición efectiva: 49 s acumulados de `render_frame + Present`.
- Warm-up global: 5 s fuera de estadísticas.
- Settle por fase: 0,75 / 1,00 / 1,00 / 1,25 s fuera de estadísticas.
- Duración nominal de la fase GPU: 58 s más overhead pequeño de telemetría/UI.
- FPS/1% Low: derivados exclusivamente de frametimes reales medidos.
- GPU frametime: D3D11 TIMESTAMP + TIMESTAMP_DISJOINT. Si la query no es válida, se descarta; no se sustituye por CPU frametime.
- Cobertura timestamp: limitada por definición a 0–100 %.

## Corrección del 1% Low

En V171, `PeekMessage` y la lectura no bloqueante de `GetData` podían ejecutarse dentro de la región `frame_start → frame_end`. V172 mueve esos trabajos fuera del cronómetro. También cambia el cierre de cada fase: ya no se detiene porque hayan transcurrido N segundos de pared incluyendo callbacks, sino cuando se han acumulado N segundos reales de render + Present.

La cámara, el agua y las animaciones de la ventana medida avanzan con un reloj determinista basado en la duración objetivo de las fases y en el tiempo de render acumulado, no con el tiempo de pared del proceso. Esto evita que equipos más lentos recorran una ruta distinta.

Los spikes no se eliminan del resultado. V172 publica además:

- frametime mediano;
- umbral de spike (`max(2× mediana, mediana + 4 ms)`);
- cantidad de frames por encima del umbral;
- ratio de spikes.

Esto permite distinguir un 1% Low realmente malo de una medición contaminada sin esconder muestras.

## Cambios visuales

### Árboles

- Tronco y ramas cónicas reales.
- Canopy formado por clusters de tarjetas cruzadas.
- Alpha cutout procedural para romper la silueta rectangular.
- Textura procedural de corteza multiescala.
- Variación determinista de tamaño, rotación y color por instancia.
- Movimiento leve de viento sólo sobre follaje.

### Agua

- Cuatro ondas direccionales en vertex shader.
- Micro-normal combinada desde tres escalas de textura procedural.
- Fresnel.
- Reflejo procedural del cielo según vector reflejado.
- Especular solar.
- Color por profundidad y espuma cerca de costa usando la altura real del terreno.

### Terreno

- Mezcla multiescala de arena, pasto y roca.
- Mezcla por altura y pendiente.
- Oscurecimiento húmedo cerca de costa.

## Workload estándar aproximado

| Escena | Triángulos/frame | Árboles | Rocas | Nubes | Shader iters | Texture samples |
|---|---:|---:|---:|---:|---:|---:|
| Valle | 141.832 | 220 | 90 | 30 | 10 | 5 |
| Bosque | 388.564 | 980 | 300 | 52 | 20 | 9 |
| Lago | 807.352 | 2.300 | 720 | 78 | 38 | 16 |
| Extreme | 1.539.524 | 4.600 | 1.500 | 118 | 64 | 24 |

Los conteos son derivados de los meshes y cantidades realmente enviadas al renderer; no son un score.

## Pruebas ejecutadas en entorno de construcción

- `tests/test_v172_benchmark_v10_realistic_isolated.py`: **11/11 PASS**.
- `tests/test_v168_directx_fake_com_smoke.py`: **1/1 PASS**.
- Pruebas de timestamp V169 compatibles con metodología actual (`-k 'not method_ids and not renderer_returns'`): **5/5 PASS**.
- `compileall`: **PASS**, 403 archivos Python compilados.
- Meshes de árbol/agua: índices válidos y triangulación consistente.
- Política REAL_OR_NA: preservada.

## Límite de esta validación

El entorno de construcción no dispone de un dispositivo Direct3D 11 de Windows, por lo que no puede certificar el resultado visual ni el comportamiento del driver físico. La validación final debe realizarse en Windows ejecutando `Probar_Benchmark_GPU_V10.bat` y revisando `benchmark_gpu_v10_ultimo_resultado.json`.

En esa prueba física deben comprobarse especialmente: cobertura GPU timestamp, 1% Low, spike ratio, GPU frametime vs CPU/Present, uso/temperatura reales y ausencia de artefactos gráficos.
