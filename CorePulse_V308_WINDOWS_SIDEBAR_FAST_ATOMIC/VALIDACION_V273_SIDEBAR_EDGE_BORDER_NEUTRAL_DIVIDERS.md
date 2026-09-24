# VALIDACIÓN V273 — Sidebar Edge Border + Neutral Dividers

Base exacta: V272.

Cambio visual solicitado:
- V272 colocaba el borde exterior con `inset = 8`, por lo que el rectángulo quedaba visualmente metido dentro del sidebar.
- V273 elimina ese inset y ancla los cuatro trazos Tk nativos de 2 px al perímetro real del `app.sidebar`.
- Superior e izquierdo parten en `x=0 / y=0`; inferior y derecho se alinean al extremo real mediante `rely/relx=1.0` y un desplazamiento de `-thickness`.
- Se mantienen los separadores internos de V272 con `COLORS["border"]`; no vuelve el celeste brillante.
- No se modifica el fondo del sidebar, botones, navegación, footer, Temas, Actualizaciones o comportamiento responsivo.
- No se modifica telemetría, SMART, benchmark, diagnóstico ni los contratos `REAL_OR_NA` / `REAL_FPS_OR_NA_ONLY`.
