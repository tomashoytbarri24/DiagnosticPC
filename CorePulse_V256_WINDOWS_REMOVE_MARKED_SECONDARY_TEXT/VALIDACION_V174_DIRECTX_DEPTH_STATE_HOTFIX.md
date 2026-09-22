# Validación V174 — DirectX depth-state hotfix

V173 fallaba físicamente en Windows durante `first_scene_frame` con `access violation reading 0x0000000000000000`.

## Causa

La constante `CTX_OM_SET_DEPTH_STENCIL_STATE` apuntaba al slot 34 del vtable de `ID3D11DeviceContext`. Ese slot corresponde a `OMSetRenderTargetsAndUnorderedAccessViews`; `OMSetDepthStencilState` está en el slot 36. Llamar al slot 34 con la firma de dos argumentos del depth-state produce una llamada ABI inválida y puede terminar en access violation.

## Corrección

- `CTX_OM_SET_DEPTH_STENCIL_STATE = 36`.
- Se mantiene sin cambios el renderer V11, materiales, escenas, tiempos, timestamps GPU y política REAL_OR_NA.
- Se añadió una regresión que fuerza el camino `depth_readonly` y verifica que el método correcto se invoque durante un frame completo simulado.

## Alcance

Este hotfix no modifica el workload ni el score. Corrige únicamente el enlace COM que V173 introdujo al añadir depth-state de solo lectura para cielo y nubes.
