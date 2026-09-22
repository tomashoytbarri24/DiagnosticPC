# V222 — Edge Arrow Global Hit-Zone Fix

## Problema
En V221 la flecha podía verse, pero seguía siendo difícil/imposible de presionar porque el click dependía del hit-test del widget flotante y la cascada podía moverse al cambiar la opción vertical activa.

## Corrección
- Se agrega una **zona de click global** alrededor de la flecha.
- El click para abrir/cerrar ya no depende de que el `CTkButton` reciba físicamente el evento.
- Al mover el cursor desde el borde hacia la flecha, la opción activa queda **bloqueada** para que la cascada no cambie de posición.
- Se aumenta ligeramente el área visual/interactiva de la flecha sin volverla invasiva.
- Se conserva el sidebar completamente oculto cuando está colapsado.
