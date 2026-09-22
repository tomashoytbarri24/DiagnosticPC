# V181 — Benchmark V13 · Safety propagation + UI settle

## Hallazgos del video V180

- El benchmark completó GPU, CPU, RAM y SSD sin crash.
- `EN EJECUCIÓN` se mantuvo correctamente en 97 % y pasó a `ÚLTIMO RESULTADO` al 100 %.
- El vacío grande de V179 desapareció.
- Durante el primer desplazamiento de los resultados se observaron restos visuales transitorios: encabezado parcialmente cortado y textos/tarjetas duplicados durante uno o dos frames antes de estabilizarse.
- La evidencia térmica mostró CPU a 100.0 °C y margen mínimo TjMax 0.0 °C. Ese mínimo por sí solo no demuestra 3 muestras consecutivas <=1.0 °C; V181 añade la evidencia exacta del gatillo para distinguir pico aislado de condición sostenida.

## Cambios

1. La prueba DirectX recibe el `should_stop` combinado del suite, no sólo cancelación del usuario. Si el monitor activa SAFETY_STOP, el renderer puede salir de la escena en curso.
2. La auditoría CPU expone `safety_observation`: muestras <=1.0 °C, racha consecutiva máxima, requisito de 3 y `trigger_observed`.
3. La UI muestra esa evidencia del gatillo sin inferencias.
4. Tras el swap atómico de resultados se recalcula la geometría del StableScrollHost y se fuerzan repintados fuertes inmediatos y diferidos para limpiar píxeles viejos antes del primer scroll.

## Fuera de alcance

No se retocan agua, vegetación, aviones, shaders ni complejidad visual. Ese pulido se retoma después de validar V181.
