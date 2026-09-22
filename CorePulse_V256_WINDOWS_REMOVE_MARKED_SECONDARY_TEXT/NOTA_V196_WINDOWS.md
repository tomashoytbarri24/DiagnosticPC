# CorePulse V196 Windows — Benchmark GPU V19

Base canónica: V195 Windows. La preview Linux anterior queda fuera de esta rama.

## Objetivo
Cerrar los defectos de presentación observados en la ejecución real de V195 sin reabrir la arquitectura estable del dashboard.

## Cambios
- GPU V19 por cambio material del escenario visual.
- Jets con formación tridimensional determinista y detalle posterior.
- Agua/costa con menor periodicidad visible.
- Vegetación con variación morfológica determinista.
- Historial menos denso y primera pintura más rápida.
- Evidencia más directa con abrir carpeta/copiar ruta.

## Reglas preservadas
- `REAL_OR_NA` / `REAL_FPS_OR_NA_ONLY`.
- 49 segundos medidos en perfil estándar GPU.
- VSync OFF, wall-clock y timestamps GPU auditados.
- Seguridad térmica y `SAFETY_STOP` sin cambios.
