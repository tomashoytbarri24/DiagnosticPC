# VALIDACIÓN V275 — SIDEBAR FOOTER FLOW FIX

## Base
- Proyecto base: V274

## Objetivo
- Corregir la composición visual de la parte baja del sidebar (bloque Personalización).

## Cambios realizados
- En el layout base, Personalización deja de estar forzada como footer fijo.
- El bloque ahora fluye inmediatamente después de Historial en ventanas con alto normal.
- Solo se vuelve footer fijo en layouts verticalmente ajustados, para evitar recortes.
- Se reducen márgenes inferiores de la versión y del bloque para un cierre más limpio.

## Impacto esperado
- Desaparece el efecto de bloque "flotando" o demasiado separado en la parte baja.
- La transición Historial → Personalización se ve continua y coherente.
- No hay cambios funcionales.

## Verificaciones recomendadas
1. Abrir la ventana principal en tamaño normal.
2. Confirmar que Personalización queda inmediatamente bajo Historial.
3. Reducir la altura de la ventana y confirmar que el bloque sigue siendo visible y no se corta.
