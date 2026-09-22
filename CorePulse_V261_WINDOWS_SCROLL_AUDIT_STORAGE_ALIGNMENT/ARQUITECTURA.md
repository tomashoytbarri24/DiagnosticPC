# Arquitectura actual de CorePulse V261

CorePulse V261 conserva la arquitectura Windows limpia heredada de V257/V258.

## Capas principales

- `gui/`: dashboard, Centro de salud, Benchmark, Audio, Temas y Actualizaciones.
- `core/`: telemetría, salud, benchmark, Windows health, drivers, historial y servicios.
- `tools/`: dependencias ejecutables necesarias, incluido PresentMon.

## Integraciones V261

### Benchmark
El motor V25 no cambia. La UI no reserva resultados antes de ejecutar y usa `StableScrollHost` con backend Canvas para las páginas posteriores a la medición.

### Driver Hub
`core/driver_updates.py` identifica hardware relevante, obtiene IDs PnP, consulta el Microsoft Update Catalog, descarga paquetes de Microsoft y usa PnPUtil como autoridad final de instalación. La UI ofrece descarga/instalación individual o masiva y oculta el inventario técnico hasta que el usuario lo solicite.

### Dashboard
No se construye la antigua tarjeta de Estado del agente del header. El agente sigue ejecutándose y alimentando alertas/estado; sólo se elimina esa representación redundante.


## V261 — autoridad de scroll

Todas las vistas desplazables de la UI usan `gui.stable_scroll.StableScrollHost`. El backend `place` es preferido para páginas CTk densas porque mueve un único frame; los resultados de Benchmark mantienen `canvas` para preservar el drag validado de la barra vertical. La rueda usa 96 px como velocidad base.
