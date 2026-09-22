# Validación V200 — Result Clarity + Aircraft Framing

## Alcance

V200 parte de V199 Windows. Se corrigen dos problemas observados en la validación real: contenido de resultados que podía quedar fuera de la altura visible, y jets demasiado lejanos durante el benchmark gráfico.

## Resultados sin recorte

- `Resumen`, `GPU 3D`, `Sistema` y `Evidencia` siguen siendo páginas preconstruidas independientes.
- La navegación permanece fija.
- Cada página usa su propio `StableScrollHost` con backend `place`.
- Al cambiar de pestaña, la vista comienza arriba y recalcula su geometría.
- Expandir detalles reconstruye únicamente la página activa con su viewport propio.
- El contenido puede crecer más allá de 1280×800 sin quedar inaccesible.

## Benchmark GPU V20

El workload se versiona a V20 porque cambia el encuadre espacial de los jets.

Se preserva:
- geometría base de `directx_scene.py` byte por byte respecto a V199;
- instancias por escena: 3 / 6 / 9 / 12 jets;
- 7 draw calls por frame;
- 10 + 12 + 12 + 15 = **49 s medidos**;
- wall-clock;
- FPS y 1% Low reales;
- timestamps GPU;
- `REAL_OR_NA` / `REAL_FPS_OR_NA_ONLY`;
- `SAFETY_STOP`.

V20 acerca la formación, reduce ligeramente su dispersión y aumenta su tamaño aparente. No debe compararse como metodología equivalente con V19.

Resultado persistente: `resultados/benchmark_gpu_v20_ultimo_resultado.json`.

## Pruebas

- V200 específicas: **6 PASS**.
- Seguridad térmica / propagación vigente: **10 PASS** (guard histórico de hashes V13 excluido).
- Knowledge Clarity V199 vigente: **3 PASS** seleccionados.
- Knowledge Layer V198 vigente: **6 PASS** seleccionados.
- UX Closure V197 vigente: **3 PASS** seleccionados.
- Unified live-health instant condition: **PASS**.
- Total funcional relevante verificado: **29 PASS**.
- `python -m compileall -q core gui tools`: **PASS**.

## Límite de esta validación

El entorno de construcción no ejecuta la ventana Direct3D 11 de Windows. El nuevo encuadre de jets debe validarse visualmente en Windows mediante una ejecución real; no se simulan FPS ni capturas del renderer.
