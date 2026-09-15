# Validación V134

- Versión centralizada: V134 / `COREPULSE_CAPABILITY_SELF_DIAGNOSTICS`.
- Centro de Salud incorpora módulo `CorePulse` sin añadir carga al sidebar ni alterar el responsive de V133.
- El autodiagnóstico usa `collect_readiness()` y `build_sensor_diagnostics()`; no inventa disponibilidad ni valores.
- Dependencias obligatorias fallidas => `ERROR`; capacidades opcionales ausentes => `N/A`.
- El probe completo se ejecuta en background al abrir la vista.
- Se persiste `corepulse_capabilities.json` para soporte técnico.
- Runtime canónico y SMART/NVMe no cambian.
