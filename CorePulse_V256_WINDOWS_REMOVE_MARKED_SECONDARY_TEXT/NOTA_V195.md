# CorePulse V195 — Benchmark GPU V18 Professional Finish

Base directa: V194.

## Problemas confirmados en video V194
- Al cambiar `Resumen → GPU 3D → Sistema`, el dashboard destruía y reconstruía widgets CTk y dejaba tarjetas/textos duplicados durante varios frames.
- Historial podía tardar varios segundos mientras leía decenas de sesiones en el hilo gráfico.
- V194 ya usaba persistencia V17, pero algunos textos/HUD operativos seguían rotulados V16.
- Los jets V17 seguían leyendo como líneas horizontales a distancia.

## V195
- Dashboard con cuatro páginas persistentes; cambio de vista sin reconstrucción total.
- Historial cargado fuera del hilo Tk y render progresivo de 5 sesiones.
- Identidad centralizada en V18.
- Jets en formación V determinista y con contraste atmosférico reforzado.
- `REAL_OR_NA`, seguridad térmica, wall-clock y telemetría real sin sustituciones.
