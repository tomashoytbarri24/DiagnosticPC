# V223 — Windows Mainline · Sidebar Visual Cleanup + Status Fit

## Objetivo
Corregir los fallos visuales observados en V222 sin abandonar la idea de sidebar oculto con aparición contextual por posición.

## Cambios aplicados
- Se elimina la acumulación de labels/bloques del sidebar al cerrar y volver a abrir.
- La cascada deja de mostrar varios controles separados: ahora usa sombras superpuestas + una cápsula compacta con icono y flecha.
- La cápsula ocupa menos espacio sobre el contenido principal.
- La zona de click distingue icono (abre y navega) de flecha (sólo restaura sidebar).
- El hover del borde se estrecha para no invadir el dashboard.
- El Resumen acorta textos secundarios y mejora wrap de estado/supervisión/trazabilidad.

## Política
- Se mantiene REAL_OR_NA.
- No se altera telemetría ni autoridad diagnóstica.
