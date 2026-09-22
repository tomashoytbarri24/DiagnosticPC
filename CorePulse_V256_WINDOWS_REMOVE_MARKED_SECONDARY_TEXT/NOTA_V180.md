# V180 — Benchmark V13 · seguridad CPU + publicación UI atómica

V180 parte exactamente de V179. **No modifica el workload visual V13**: escenas, shaders, geometría, complejidad, resolución, warm-up, settle, prime, reloj de pared, FPS, 1% Low y timestamps GPU permanecen intactos.

## Cambios

- CPU: cuando existe una **distancia a TjMax real**, la protección térmica sostenida pasa de `<= 0,5 °C` a `<= 1,0 °C` durante 3 muestras reales consecutivas.
- Si el sensor TjMax no existe, se conserva el fallback extremo existente; no se inventa un TjMax.
- GPU: no cambia la política V179. Un límite térmico real reportado por el dispositivo tiene prioridad; si no existe, queda N/A y se conserva el fallback extremo.
- UI: al terminar el benchmark, el cuerpo completo del Centro de Salud ya no se destruye/reconstruye. Los resultados se construyen en un host de staging no visible y se publican juntos al finalizar.
- La etiqueta de estado cambia a `EN EJECUCIÓN` durante progreso real y a `ÚLTIMO RESULTADO` al publicar el resultado.
- Se conserva `REAL_OR_NA` y la auditoría térmica V179.

## Orden de trabajo

El pulido de agua, vegetación y efectos queda deliberadamente fuera de V180. Primero se valida seguridad + transición; después se retoma el acabado visual del benchmark V13.
