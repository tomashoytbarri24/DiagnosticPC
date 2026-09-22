# VALIDACIÓN V243 — Trends Wrapper Card Parity

- Base: V242 stable.
- Cambio aplicado: la tarjeta contenedora de tendencias (`frame_charts`) ahora usa el mismo `corner_radius=16` que las tarjetas de CPU, RAM, GPU y almacenamiento.
- Archivos tocados:
  - `main.py`
  - `gui/dashboard.py`
  - `gui/dashboard_layout.py`
- No se modificó telemetría, sensores ni la lógica de render de gráficos.
