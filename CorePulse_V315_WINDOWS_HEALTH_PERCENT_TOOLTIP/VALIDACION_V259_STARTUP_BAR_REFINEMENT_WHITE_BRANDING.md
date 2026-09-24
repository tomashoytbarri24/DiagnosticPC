# VALIDACION V259

- Base: V257.
- Cambio visual únicamente en `gui/startup_gate.py`.
- Tarjeta de inicio con `corner_radius=0`.
- Eliminado el label `self.percent`; la barra ocupa todo el ancho disponible.
- `update_stage()` sigue mostrando progreso real, ahora sólo sobre la barra.
- Sin cambios en telemetría, diagnóstico, benchmark ni lógica REAL_OR_NA.
