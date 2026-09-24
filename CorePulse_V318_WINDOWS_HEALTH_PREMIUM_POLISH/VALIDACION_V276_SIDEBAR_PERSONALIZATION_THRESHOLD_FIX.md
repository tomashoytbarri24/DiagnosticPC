# VALIDACIÓN V276 — SIDEBAR PERSONALIZATION THRESHOLD FIX

## Base
- Proyecto base: V275

## Objetivo
- Evitar que el bloque Personalización quede anclado al fondo en ventanas con altura normal.

## Cambios realizados
- Ajustado el umbral de `personalization_tight` en `gui/dashboard_layout.py` de `< 940` a `< 760`.
- Con ello, el bloque Personalización solo pasa a modo footer fijo en ventanas realmente bajas o en layout compacto.

## Impacto esperado
- En tamaño normal, la sección Personalización debe quedar inmediatamente debajo de Historial, sin hueco grande.
- En ventanas muy bajas, el bloque se sigue protegiendo contra recortes.
