# CorePulse V197 Windows — Benchmark GPU V19 UX Closure

Base directa: V196 Windows.

- Benchmark GPU permanece en V19; no cambia el workload, geometría, HLSL ni temporización.
- Historial abre con 3 ejecuciones visibles y sólo 5 sesiones precargadas para reducir el coste del primer render; el resto se carga en segundo plano.
- Textos técnicos del benchmark se vuelven más comprensibles sin ocultar evidencia: `CV` pasa a `Variación (CV)`, `spikes` a `Frames lentos`, `Present` a `Frame presentado`.
- La tarjeta térmica del resumen ofrece acceso directo a Evidencia cuando se detecta temperatura alta o un safety stop.
- Evidencia térmica expresa el conteo como `Muestras sobre X °C`, evitando la lectura ambigua `Umbral X · N muestras`.
