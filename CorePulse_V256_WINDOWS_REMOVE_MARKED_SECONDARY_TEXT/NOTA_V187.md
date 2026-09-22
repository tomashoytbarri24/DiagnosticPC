# Nota V187 — Benchmark GPU V16 UX Dashboard

V187 responde a la revisión completa del video de V186. La ejecución GPU V16 no se modifica.

## Problemas observados en V186

- La primera entrada a Benchmark podía sentirse lenta porque el clic no mostraba feedback inmediato mientras se construían dos árboles de UI pesados.
- `BenchmarkHistoryPanel` se creaba aunque el usuario nunca abriera Historial.
- Tras recopilar los datos, demasiadas métricas tenían el mismo peso visual y el resultado requería leer/scrollar mucho para entenderlo.
- La ruta JSON, compatibilidad de sensores y metodología ocupaban espacio principal pese a ser evidencia técnica.
- GPU Extreme aparecía como dato principal y de nuevo dentro del detalle de escenas.
- Temperatura máxima global y pico durante GPU podían parecer contradictorios sin una separación visual clara del alcance.
- El video V186 todavía mostró residuos/duplicados transitorios al desplazarse por la vista larga de resultados.

## Decisión V187

No se añade otro parche de repaint. La interfaz adopta divulgación progresiva: un resumen corto primero y los detalles técnicos en vistas específicas. El menor desplazamiento vertical reduce la superficie donde Windows puede exhibir residuos de pintura.

## Contrato preservado

Benchmark GPU V16, `REAL_OR_NA`, 49 s medidos, wall-clock, 1% Low, D3D11 timestamps, persistencia JSON y protección térmica permanecen sin cambios.
