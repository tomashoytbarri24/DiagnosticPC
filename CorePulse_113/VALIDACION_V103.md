# VALIDACIÓN V103

## Cambio principal
Acción directa **Limpiar RAM ahora** desde el menú de bandeja.

## Contrato
- No abre una página de CorePulse.
- No restaura la ventana principal.
- Usa `optimize_ram_safely`, que no recorta working sets de procesos externos.
- Ejecuta en hilo secundario para no bloquear la interfaz.
- Entrega notificación con MB recuperados y uso de RAM antes/después.
- Bloquea ejecuciones concurrentes de la misma acción.
- Conserva el runtime universal canónico sin cambios.

## Estado
PASS
