# VALIDACIÓN V196 WINDOWS — BENCHMARK GPU V19 VISUAL/UX FINISH

## Identidad
- App: V196.
- GPU: V19.
- JSON vigente: `resultados/benchmark_gpu_v19_ultimo_resultado.json`.

## Contrato temporal
- Valle: 10 s.
- Bosque: 12 s.
- Lago: 12 s.
- Extreme: 15 s.
- Total medido: 49 s.
- Warm-up inicial: 5 s, fuera de estadísticas.

## Workload
- Jet: 368 triángulos por mesh.
- Árbol: 328 triángulos por mesh.
- Agua: 72.962 triángulos.
- Draw calls: 7 por frame.

## UX
- Dashboard final conserva páginas preconstruidas.
- Historial publica 20 sesiones primero y precarga el resto fuera del hilo Tk.
- Cada sesión usa bloques GPU/CPU/RAM/SSD; la línea técnica extensa queda en detalle.
- Evidencia ofrece abrir carpeta/copiar ruta.

## Pruebas
- Suite específica V196: 8/8 PASS.
- Seguridad térmica V179/V180: 11/11 PASS.
- Propagación V181 excluyendo hash histórico V13: 5/5 PASS.
- Controles funcionales vigentes V195 excluyendo aserciones literales de V18: 5/5 PASS.

Los guards históricos de hashes/versiones anteriores no se consideran regresiones del workload V19.
