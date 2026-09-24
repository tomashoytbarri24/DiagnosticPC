# VALIDACIÓN V292 — GAMING TRANSPARENCY RUNTIME FIX

## Base
- Proyecto base: V291

## Problema observado
Al abrir Gaming aparecía el diálogo:
`transparency is not allowed for this attribute`

## Causa
La flecha de retorno se había dejado como `CTkButton` con `border_color='transparent'`. CustomTkinter no admite transparencia en ese atributo.

## Corrección
- La flecha ahora es un `CTkLabel` clickeable.
- No usa borde ni contenedor visual de botón.
- Conserva interacción y hover únicamente mediante cambio de color del glifo.
- El resto de V291 permanece intacto.
