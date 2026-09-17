# Validación CorePulse V166

## Objetivo
Corregir el layout del Centro de actualizaciones y eliminar la ambigüedad del contador de publicación.

## Cambios
- La tarjeta **Seguridad y recuperación** y la barra inferior de acciones ocupan filas distintas del grid.
- El bloque **Estado** deja de crecer de forma artificial cuando está vacío; mantiene una altura compacta y su propio scroll para notas largas.
- El Centro de actualizaciones ya no presenta controles superpuestos en modo ventana.
- El CTA de publicación usa **archivo(s)** en lugar de **cambio(s)**.
- La vista previa explica que el total es el número de rutas de archivo pendientes según Git, no la cantidad de ediciones manuales.
- La consola mantiene el desglose de nuevos, modificados y eliminados.

## Perfiles por equipo
Los perfiles se guardan en configuración de usuario (AppData/config) y no dentro de la carpeta distribuida de CorePulse. Por ello otro usuario/equipo no hereda el perfil de Maxi: al ejecutar la misma versión verá sus propios perfiles locales o “Sin perfiles guardados”.
