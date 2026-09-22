# Arquitectura actual de CorePulse V262

CorePulse V262 conserva la arquitectura Windows limpia heredada de V257/V258.

## Capas principales

- `gui/`: dashboard, Centro de salud, Benchmark, Audio, Temas y Actualizaciones.
- `core/`: telemetría, salud, benchmark, Windows health, drivers, historial y servicios.
- `tools/`: dependencias ejecutables necesarias, incluido PresentMon.

## Integraciones V262

### Benchmark
El motor V25 no cambia. La UI no reserva resultados antes de ejecutar y usa `StableScrollHost` con backend Canvas para las páginas posteriores a la medición.

### Driver Hub
`core/driver_updates.py` identifica hardware relevante, obtiene IDs PnP, consulta el Microsoft Update Catalog, descarga paquetes de Microsoft y usa PnPUtil como autoridad final de instalación. La UI ofrece descarga/instalación individual o masiva y oculta el inventario técnico hasta que el usuario lo solicite.

### Dashboard
No se construye la antigua tarjeta de Estado del agente del header. El agente sigue ejecutándose y alimentando alertas/estado; sólo se elimina esa representación redundante.


## Scroll heredado de V261

Todas las vistas desplazables de la UI usan `gui.stable_scroll.StableScrollHost`. El backend `place` es preferido para páginas CTk densas porque mueve un único frame; los resultados de Benchmark mantienen `canvas` para preservar el drag validado de la barra vertical. La rueda usa 96 px como velocidad base.


## Publicación Git V262

La rama local dejó de ser la autoridad del destino. `core/developer_publisher.py` construye el commit sobre el HEAD remoto seleccionado (`origin/main`, `origin/maxi/corepulse-dev`, etc.) usando un índice temporal. La operación no cambia checkout, HEAD ni staging y sólo añade la carpeta de versión. `.github` permanece bajo control del repositorio y no se modifica desde CorePulse.
