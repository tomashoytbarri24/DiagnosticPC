# V224 — Static Sidebar Stability Revert

## Objetivo
Descartar completamente el experimento de sidebar plegable, cascada contextual, flechas flotantes y hover global.

## Cambios
- Sidebar fijo y siempre visible.
- Sin botón de ocultar/mostrar.
- Sin cascada de iconos.
- Sin hit-zones globales ni bindings de hover en el borde.
- Se conservan el tamaño de ventana estilo Steam y el pulido visual del dashboard/status de V223.
- Se mantienen métodos de compatibilidad como no-op para evitar romper llamadas antiguas.

## Política
- REAL_OR_NA sin cambios.
- Telemetría y diagnóstico sin cambios.
