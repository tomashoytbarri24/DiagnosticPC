# Validación V137 — Historial de benchmark 2.0

- Vista dedicada `Ejecutar / Historial` dentro de Benchmark.
- Reutiliza `benchmark_sessions` existente; no crea una segunda fuente de datos.
- Filtros por perfil/componente y detalle de sesión.
- Renderer OpenGL y duración visibles cuando existen.
- Comparación porcentual sólo entre sesiones equivalentes y sólo con valores reales no nulos.
- Las nuevas sesiones persisten renderer en `hardware_json`.
- Política `REAL_OR_NA` preservada.
- Runtime canónico y SMART/NVMe sin modificaciones.
