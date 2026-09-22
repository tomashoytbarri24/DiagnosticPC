# CorePulse V184 — Benchmark GPU V16 Visual Cleanup

Base: V183 / Benchmark GPU V15.

- Se crea V16 porque cambia el recorte/orientación del follaje.
- Metadata runtime completa unificada a V16.
- Follaje: mismo número de tarjetas, triángulos, instancias y draw calls; planos más estrechos/asimétricos y huecos deterministas usando la misma muestra de textura.
- Evidencia térmica rotulada explícitamente como fase GPU.
- UI de resultados: settle corto + idle de StableScroll; sin update() reentrante ni repaints tardíos de 420/900 ms.
- Agua, 49 s medidos, wall-clock, FPS/1% Low, timestamps GPU, REAL_OR_NA y seguridad térmica se conservan.

Último resultado: `resultados/benchmark_gpu_v16_ultimo_resultado.json`.
