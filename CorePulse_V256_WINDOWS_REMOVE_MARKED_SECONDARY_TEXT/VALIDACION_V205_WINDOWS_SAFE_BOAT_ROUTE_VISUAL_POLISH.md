# V205 — Windows Mainline · Benchmark GPU V25 · Safe Boat Route + Continued Visual Polish

## Objetivo
Corregir el defecto observado en uso real donde el barco seguía entrando a una isla, y continuar el pulido visual incremental del benchmark.

## Cambios aplicados
- **GPU benchmark pasa a V25**.
- La trayectoria del barco se rediseña para mantenerse sobre una zona del archipiélago con altura de terreno siempre bajo el nivel del agua.
- La estela del barco se recalibra para coincidir con esa nueva trayectoria.
- Se refuerza levemente espuma/costa y se reduce un poco más la niebla para mejorar lectura.

## Política
- Se mantiene **REAL_OR_NA**.
- Se conservan los **49 s medidos** en perfil estándar.
- No se inventan métricas ni se alteran los contratos de medición.
