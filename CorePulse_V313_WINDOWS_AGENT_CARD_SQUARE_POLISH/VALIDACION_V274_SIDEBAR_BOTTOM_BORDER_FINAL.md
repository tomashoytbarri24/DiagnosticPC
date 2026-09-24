# VALIDACIÓN V274 — SIDEBAR BOTTOM BORDER FINAL

## Base
- Proyecto base: V273

## Objetivo
- Corregir únicamente el cierre visual del borde inferior del sidebar.

## Cambios realizados
- Reanclaje de las 4 líneas nativas del borde del sidebar usando `place(..., anchor=...)`.
- El borde inferior ya no usa desplazamiento negativo (`y=-thickness`).
- Reducción leve del margen inferior del bloque Personalización y de la etiqueta de versión para no alejar visualmente el cierre inferior.

## Impacto esperado
- El borde inferior del sidebar debe verse alineado con los lados izquierdo/derecho y sin apariencia de borde metido hacia adentro.
- No hay cambios funcionales.

## Verificaciones recomendadas
1. Abrir la ventana principal en modo normal.
2. Revisar el sidebar completo, especialmente la franja inferior.
3. Confirmar que el borde inferior cierra el rectángulo al ras.
4. Confirmar que Temas / Actualizaciones siguen visibles.
