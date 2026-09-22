# Nota V190 — CorePulse Finish

V190 cierra la etapa de integración visual del Benchmark V16 antes de volver a modificar el workload 3D.

## Objetivo
Que Benchmark se sienta parte nativa de CorePulse: legible de un vistazo, consistente en tamaños, bordes, radios, color y jerarquía, sin perder la evidencia técnica disponible en vistas secundarias.

## Cambios principales
- Escala tipográfica propia y consistente dentro de Benchmark.
- HUD CorePulse más grande y limpio.
- Cursor DirectX oculto desde la propia ventana con `WM_SETCURSOR`.
- Resultado con tarjetas y estados más claros, sin saturación cromática.
- `Prueba actual / Historial` como navegación superior.
- Mensajes térmicos instantáneos en ámbar mientras se confirma persistencia.

## Metodología
Benchmark GPU permanece en V16. No se cambian escenas, geometría, HLSL, tiempos ni cálculo de FPS/1% Low. El cambio de `directx_benchmark.py` se limita a eventos de cursor/ventana ejecutados fuera del intervalo de frametime medido.

## REAL_OR_NA
Se conserva íntegramente. El HUD sólo muestra FPS si el callback DirectX aporta una cifra real; warm-up/settle permanecen N/A.
