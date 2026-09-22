# V204 — Windows Mainline · Benchmark GPU V24 · Visual Scene Polish

## Objetivo
Responder al feedback visual real del benchmark:

1. El barco seguía viéndose bug / poco claro.
2. El humo se veía mediocre.
3. Árboles, piedras y mar necesitaban más trabajo visual.

## Cambios aplicados
- **GPU benchmark pasa a V24**.
- Se crea una **estela procedural del barco** en el agua.
- El **barco** usa una ruta más cercana y una escala mayor.
- El **humo** deja de reutilizar el mesh de nube y usa una **pluma apilada propia**.
- La **fogata** usa un mesh propio de llama y un shader más brillante.
- El **agua** gana mayor profundidad, brillo, espuma y contraste.
- Los **árboles** mejoran contraste perceptual del follaje y tronco.
- Las **rocas** ahora tienen ruido, musgo y lectura de material.
- Se reduce la niebla excesiva para evitar el look lavado.

## Política
- Se mantiene **REAL_OR_NA**.
- Se conservan los **49 s medidos** en perfil estándar.
- No se inventan métricas ni se reemplaza medición real.
