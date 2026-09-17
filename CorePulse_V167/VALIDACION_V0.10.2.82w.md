# Validación V0.10.2.82w — Hover Details Action Refinement

Cambio acotado a presentación del Dashboard:
- CPU, RAM y GPU mantienen la tarjeta completa clickeable.
- `Ver detalles` está oculto en reposo y aparece sólo con hover.
- Almacenamiento adopta el mismo patrón sin modificar sus datos ni su navegación.
- La salida de la tarjeta se confirma mediante posición real del puntero para evitar flicker entre hijos.

No se cambian sensores, muestreo, REAL_OR_NA, REAL_FPS_OR_NA_ONLY, diagnóstico, almacenamiento seguro ni rollback.
