# V219 — Windows Mainline · Edge Hover Cascade Sidebar

## Objetivo
Pulir el ocultamiento total del sidebar para que el botón no sea invasivo y, cuando el panel esté oculto, aparezcan sólo la flecha y el icono contextual según la altura del mouse.

## Cambios aplicados
- El botón de colapso visible deja de estar fijo: ahora sólo aparece al acercar el mouse al divisor del sidebar.
- Cuando el sidebar está oculto, acercar el cursor al borde izquierdo muestra una vista contextual mínima.
- La vista contextual enseña sólo el icono correspondiente a la zona vertical del mouse, más una flecha de restauración.
- La aparición usa una pequeña cascada visual (ghost → icono → flecha) en vez de desplegar toda la barra.
- Al reabrir el sidebar se limpia la vista contextual antes de restaurar el panel para evitar glitches visuales.

## Política
- Se mantiene **REAL_OR_NA**.
- No cambia telemetría ni lógica de diagnóstico; sólo navegación y comportamiento visual del sidebar.
