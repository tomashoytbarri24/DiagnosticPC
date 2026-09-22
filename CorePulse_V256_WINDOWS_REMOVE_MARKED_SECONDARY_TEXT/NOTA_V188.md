# CorePulse V188 — Benchmark GPU V16 UX/HUD Fix

V188 es una iteración de interfaz sobre V187. No cambia el workload GPU V16 ni los cálculos del benchmark.

## Objetivos

- Recuperar el HUD visible sin contaminar el swap-chain ni la región cronometrada.
- Eliminar el cursor ocupado durante la fase DirectX.
- Hacer el resultado entendible sin recorrer una configuración ya usada.
- Reducir el scroll largo que todavía exponía ghosting de widgets en Windows.

## HUD REAL_OR_NA

El HUD consume el callback de progreso ya existente. Si existe un FPS real medido lo muestra; durante warm-up/estabilización se publica `FPS N/A`. No interpola ni simula valores.

## Resultado compacto

Después de completar una ejecución se ocultan `Qué medir` y `Ejecutar`. El usuario puede repetir la misma selección o volver a cambiar componentes desde el Resumen. La compatibilidad detallada de sensores se crea sólo al pulsar `Ver sensores`.
