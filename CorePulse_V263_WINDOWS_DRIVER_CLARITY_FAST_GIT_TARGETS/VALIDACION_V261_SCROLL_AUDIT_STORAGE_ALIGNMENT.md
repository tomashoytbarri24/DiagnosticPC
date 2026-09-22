# Validación V261 — Scroll Audit & Storage Alignment

## Objetivo

Corregir la posición de la salud de almacenamiento observada en V260 y normalizar el desplazamiento de todas las vistas largas sin modificar el motor Benchmark V25 ni Driver Hub.

## Cambios comprobados

- La insignia `Salud xx%` comparte el slot derecho con `Ver detalles`; el botón se superpone sólo durante hover y no reserva espacio permanente.
- `StableScrollHost` usa 96 px por paso de rueda y 150 ms de retención de estado de scroll.
- Las páginas CTk densas usan backend `place` para mover un único frame y reducir el coste de repintado.
- Los resultados de Benchmark conservan backend `canvas`, validado desde V259 para arrastrar la barra vertical, con velocidad elevada de 54 a 96 px.
- Temas, publicación Git e historial de Benchmark ya no usan `CTkScrollableFrame`.
- No quedan usos de `CTkScrollableFrame` en `gui/`.

## Áreas auditadas

- Centro de salud / Driver Hub
- Benchmark (configuración y resultados)
- Historial de Benchmark
- CPU / GPU / RAM
- Red avanzada
- Tweaks Windows 11 / restauración
- Gaming / Overlay
- Alertas / historial / tendencias
- Telemetría detallada
- Temas
- Subir mi versión
- Scroll interno de almacenamiento del Resumen (conserva Canvas por ser un viewport pequeño, pero hereda la velocidad común)

## Integridad

- 149 archivos Python compilados sin errores.
- `pytest`: 7/7 pruebas aprobadas.
- `benchmark_engine.py`, `directx_benchmark.py`, `directx_scene.py` y `benchmark_version.py`: SHA-256 idénticos a V260.
- `driver_updates.py`: SHA-256 idéntico a V260.
