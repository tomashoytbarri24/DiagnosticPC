# VALIDACIÓN V106

## Objetivo
Reemplazar el benchmark demasiado corto por una suite sostenida y medible, sin overclock ni rankings ficticios.

## Cobertura
- CPU: single-thread + multinúcleo SHA-256.
- RAM: copia sostenida durante una ventana temporal.
- SSD: escritura y lectura secuencial con archivo temporal + fsync.
- GPU: workload OpenGL real en Windows, con renderer/vendor informados.
- Progreso en vivo y muestreo térmico durante la suite.
- Seguridad: detención por CPU >= 96 °C o GPU >= 92 °C cuando existe telemetría real.
- Runtime canónico: no modificado.

## Estado
PASS
