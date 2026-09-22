# CorePulse V183 — Benchmark GPU V15 Visual Optimized

V183 parte de V182/V14. Mantiene agua V14 y toda la lógica REAL_OR_NA, wall-clock, timestamps GPU y seguridad térmica.

Cambios:
- Benchmark visual pasa a V15 porque cambia de nuevo el workload gráfico.
- Follaje: 3 leaf cards a 60° por cluster en lugar de 4 a 45°, recorte más aireado y una lectura de textura menos por píxel.
- Aviones: alas/estabilizadores/deriva más legibles y formación algo más cercana, sin cambiar instancias ni draw calls.
- UI: settle/repaint reforzado para eliminar residuos transitorios durante el primer scroll de resultados.
- JSON: `resultados/benchmark_gpu_v15_ultimo_resultado.json`.
