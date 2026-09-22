# V179 — Benchmark V13 · cierre UI + auditoría térmica REAL_OR_NA

## Alcance
V179 parte exactamente de V178. No modifica `core/directx_benchmark.py`, `core/directx_scene.py`, escenas, shaders, complejidad, tiempos, warm-up, settle, prime, FPS, 1% Low ni timestamps GPU.

## Cierre de interfaz
- El estado usa el progreso parcial como evidencia de ejecución: no debe aparecer `LISTO` con 97 %.
- Al terminar, el callback publica primero el resultado y conserva el 100 %/ruta; `_async` realiza un único render estable.
- Se elimina el `self._render()` adicional que podía provocar una transición vacía antes de mostrar resultados.

## Auditoría térmica
El JSON V13 conserva las muestras originales y agrega `telemetry.thermal_audit`:
- CPU: pico, observaciones ≥95 °C, mayor tramo entre muestras consecutivas calientes, distancia mínima real a TjMax cuando existe.
- GPU del renderer: pico core/hotspot, observaciones ≥88 °C, límite core/hotspot sólo si un sensor real lo reporta y margen mínimo observado a ese límite.
- Los tramos son diferencias entre timestamps de muestras consecutivas reales. No se afirma temperatura continua entre lecturas.
- Si TjMax o el límite térmico GPU no está disponible, queda `null`/N/A.

La carga gráfica y sus tiempos no cambian. La protección sí corrige dos casos de seguridad: una distancia real a TjMax de `0.0 °C` ya no puede perderse por evaluación booleana, y un límite térmico GPU reportado por sensor puede activar la parada tras 3 muestras consecutivas. Si la GPU no expone límite, se conserva el fallback extremo sostenido de 95 °C.

## Validación
`python -m unittest tests.test_v177_benchmark_ui tests.test_v178_benchmark_v13 tests.test_v179_thermal_ui_closure -v`

Después de una ejecución real en Windows, enviar `resultados/benchmark_gpu_v13_ultimo_resultado.json` para revisar específicamente `telemetry.thermal_audit` y las muestras brutas.
