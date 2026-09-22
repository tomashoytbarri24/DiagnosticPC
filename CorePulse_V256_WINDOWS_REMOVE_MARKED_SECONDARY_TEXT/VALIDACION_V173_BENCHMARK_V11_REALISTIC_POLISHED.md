# Validación V173 — Benchmark GPU V11 · Realistic Polish + Audited Steady-State Timing

## Objetivo

V173 parte de V172, que ya renderizaba correctamente en el PC físico del usuario. Esta versión no reemplaza el backend Direct3D 11 ni cambia a otra API. El objetivo es mejorar el acabado visual y hacer más explícita la auditoría de estabilidad sin maquillar los frametimes.

## Metodología estándar

- API: Direct3D 11 hardware.
- Resolución objetivo: 1920×1080.
- VSync: OFF.
- Escenas: Valle, Bosque, Lago, Extreme.
- Medición efectiva: 49 s acumulados de `render_frame + Present`.
- Warm-up global: 5 s fuera de estadísticas.
- Settle por fase: 0,75 / 1,00 / 1,00 / 1,25 s fuera de estadísticas.
- Prime: 8 frames por escena, después del settle y antes de abrir estadísticas/queries.
- Tiempo nominal sin contar prime frames: 58 s.
- FPS/1% Low: derivados de frametimes CPU/Present reales.
- GPU frametime: D3D11 TIMESTAMP + TIMESTAMP_DISJOINT; muestra inválida => descartada/N/A.
- Cobertura timestamp: limitada a 0–100 %.
- No se eliminan spikes del cálculo final.

## Cambios visuales V11

### Nubes

Las nubes V10 usaban mallas redondeadas similares a rocas. V11 las reemplaza por grupos de tarjetas cruzadas con borde radial, ruido multiescala y alpha blending. Además se desactiva la escritura de profundidad para nubes y cielo, conservando el depth-test contra la geometría opaca.

Orden del pass visual:

1. terreno;
2. agua;
3. rocas;
4. árboles;
5. jets;
6. cielo con profundidad de sólo lectura;
7. nubes transparentes con profundidad de sólo lectura.

### Agua

- Resolución de malla: 192×192.
- Cuatro ondas direccionales deterministas.
- Pequeño desplazamiento horizontal tipo Gerstner.
- Cuatro escalas de detalle procedural para la normal.
- Fresnel.
- Reflejo procedural del cielo.
- Especular solar + glint de alta frecuencia.
- Profundidad y espuma de costa derivadas de la altura real del terreno.

### Terreno

- Mezcla multiescala arena/pasto/roca.
- Máscara por altura y pendiente.
- Micro-normal procedural derivada de muestras vecinas de la textura determinista.
- Niebla combinada por distancia y altura.

### Árboles

- Tronco y diez ramas cónicas.
- 24 clusters de foliage, con tarjetas cruzadas más pequeñas e irregulares.
- Alpha cutout procedural.
- Variación determinista por instancia y viento leve.
- Un único draw call instanciado para todos los árboles de la escena.

## Auditoría de frametime

V173 conserva todos los frames medidos. Antes de abrir estadísticas ejecuta 8 prime frames por escena para estabilizar el camino de presentación y el pipeline; esos frames quedan registrados como `measurement_prime_frames_discarded` y no se mezclan con los 49 s efectivos.

Por escena se publican además:

- FPS promedio;
- 1% Low;
- frametime promedio, mediana, p95 y p99;
- umbral, cantidad y ratio de spikes;
- `frametime_cv`;
- `frametime_max_to_median_ratio`;
- GPU frame time promedio/mediana/p95/p99;
- cobertura, dropped y disjoint de timestamp queries.

## Workload estándar derivado de las mallas

| Escena | Triángulos/frame aprox. | Árboles | Rocas | Nubes | Shader iters | Texture samples |
|---|---:|---:|---:|---:|---:|---:|
| Valle | 175.736 | 220 | 90 | 30 | 10 | 5 |
| Bosque | 472.908 | 980 | 300 | 52 | 20 | 9 |
| Lago | 985.896 | 2.300 | 720 | 78 | 38 | 16 |
| Extreme | 1.885.068 | 4.600 | 1.500 | 118 | 64 | 24 |

Meshes V11 derivados en construcción:

- árbol: 328 triángulos por instancia;
- nube: 60 triángulos por instancia;
- agua: 72.962 triángulos.

Los conteos describen el workload realmente enviado al renderer; no son un score.

## Pruebas ejecutadas en entorno de construcción

- `tests/test_v173_benchmark_v11_realistic_polished.py`: 8/8 PASS.
- `tests/test_v168_directx_fake_com_smoke.py`: 1/1 PASS junto con V173.
- Contrato de integridad (`python tests/test_integrity.py`): PASS en 12/12 verificaciones.
- `compileall`: PASS para el árbol Python de la entrega.
- Meshes V11: índices válidos y triangulación consistente.
- Política REAL_OR_NA / REAL_FPS_OR_NA_ONLY: preservada.

## Límite de esta validación

El entorno de construcción no dispone de un dispositivo Direct3D 11 de Windows, por lo que no puede certificar el aspecto final, el comportamiento del driver físico ni el impacto real sobre una RTX concreta. La validación física debe hacerse en Windows con `Probar_Benchmark_GPU_V11.bat` y `benchmark_gpu_v11_ultimo_resultado.json`.

En esa validación deben revisarse especialmente: ausencia de artefactos, aspecto de nubes/agua/árboles, GPU usage, 1% Low, CV, spike ratio, timestamp coverage y GPU frame time frente a CPU/Present.
