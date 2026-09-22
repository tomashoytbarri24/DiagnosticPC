# V202 — Windows Mainline · Benchmark GPU V22

## Hallazgos verificados en la grabación V201

1. **HUD Extreme incorrecto**: la escena `Valle completo / Extreme` aparecía como `VALLE · ESCENA 1/4` porque el detector encontraba `valle` antes de `extreme`.
2. **Barco no visible**: la posición V201 quedaba fuera del corredor de cámara y demasiado baja respecto al agua.
3. **Fogata/humo no visible**: la ubicación estaba fuera del corredor principal de Extreme y el VS colapsaba los puffs del mesh al ignorar `i.pos`.
4. **Resumen con repetición**: `Lectura rápida` y una segunda cuadrícula de tarjetas repetían las mismas métricas.

## Correcciones V202

- Benchmark GPU V22.
- HUD prioriza `extreme` antes de `valle`.
- Barco confinado al canal central de agua, centro Y elevado y escala ajustada.
- Humo en isla sur `(10, -110)` y volumen derivado de la geometría real del mesh procedural.
- Resumen rápido sin cuadrícula duplicada; no se elimina ninguna vista de detalle.
- Persistencia vigente: `resultados/benchmark_gpu_v22_ultimo_resultado.json`.

## Políticas preservadas

- `REAL_OR_NA`.
- `REAL_FPS_OR_NA_ONLY`.
- Wall-clock determinista.
- Timestamps GPU D3D11.
- Sin rankings sintéticos.
- 49 s medidos en el perfil estándar.
