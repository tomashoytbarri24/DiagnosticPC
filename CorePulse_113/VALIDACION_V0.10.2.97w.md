# VALIDACIÓN V0.10.2.97w

## Alcance
Galería interna de 10 temas con preview y aplicación global persistente.

## Criterios
- El botón lateral dice `Temas`.
- No se crea una ventana nueva: se usa `internal_navigation`.
- Existen exactamente 10 perfiles.
- La lista es desplazable.
- Seleccionar un tema sólo actualiza la vista previa.
- `Aplicar tema` guarda la preferencia y reinicia la UI para aplicar colores coherentes en módulos ya existentes.
- Migración `dark -> corepulse` y `light -> snow`.
- El bootstrap de runtime corto de 96w permanece intacto.
