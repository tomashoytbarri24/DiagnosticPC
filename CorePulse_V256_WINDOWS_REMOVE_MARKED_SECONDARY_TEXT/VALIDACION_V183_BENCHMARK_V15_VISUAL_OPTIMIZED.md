# Validación V183 — Benchmark GPU V15 Visual Optimized

- Base: V182 / Benchmark GPU V14.
- V15 se separa porque cambia el workload visual (follaje y silueta/formación de jets).
- Contrato de tiempo estándar preservado: 10 + 12 + 12 + 15 = 49 s medidos.
- Agua V14 preservada: plano 760 m y misma rejilla.
- Follaje: 3 tarjetas/cluster a 60°; árbol 328 triángulos vs 376 en V14.
- Draw calls por frame: 7 (sin aumento).
- Carga geométrica aproximada: Valle 175754; Bosque 472944; Lago 985950; Extreme 1885140 triángulos/frame.
- Persistencia: resultados/benchmark_gpu_v15_ultimo_resultado.json, sin sobrescribir V14.
- Seguridad térmica V179–V181 preservada.
- UI: settle/repaint extendido hasta 900 ms para eliminar residuos del primer scroll.
- py_compile: PASS.
- Regresión vigente: 23 PASS / 1 guard histórico V181 deseleccionado porque exige hashes V13/V180 y dejó de aplicar desde V182.
