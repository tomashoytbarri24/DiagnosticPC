# V220 — Supervisión Clip + Arrow Interaction Fix

## Correcciones
- La tarjeta **Supervisión actual** recibe más ancho relativo.
- El texto principal de alerta usa tipografía responsive más pequeña y wrap seguro en tamaños compactos.
- Se corrige un bug interno donde `_clear_sidebar_motion_layers()` reiniciaba también el estado del hover/cascada.
- La cascada ya no se reinicia en cada pixel de movimiento cuando el cursor sigue sobre la misma opción.
- La zona interactiva del borde oculto pasa a 118 px, aunque visualmente sólo se ve icono + flecha.
- La flecha tiene un área clickeable mayor pero fondo transparente para seguir siendo discreta.
- Al salir de la zona se usa una pequeña tolerancia temporal antes de ocultar la cascada.

## Política
- No cambia telemetría, diagnóstico ni REAL_OR_NA.
