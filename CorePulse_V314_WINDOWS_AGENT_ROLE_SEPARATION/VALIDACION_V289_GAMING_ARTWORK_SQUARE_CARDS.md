# VALIDACIÓN V289 — GAMING ARTWORK + SQUARE CARDS

## Base
- Proyecto base: V288

## Cambios realizados
- Recursos CPU/GPU/RAM rediseñados como tres tarjetas cuadradas.
- Bloque de juego actual ahora intenta mostrar la carátula real del juego detectado mediante la biblioteca/artwork existente.
- Se mantiene fallback visual cuando no hay juego detectado o artwork disponible.
- Perfil de rendimiento recortado verticalmente para ganar aire visual.

## Verificación sugerida
1. Abrir Gaming > Inicio sin juego activo.
2. Abrir un juego detectado y comprobar que aparece la carátula y el nombre.
3. Confirmar que FPS siga como N/A si no hay lectura real.
