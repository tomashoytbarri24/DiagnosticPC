# VALIDACIÓN V100 — True Theme Replacement

## Objetivo
Eliminar el efecto de filtro/oscurecimiento al aplicar temas y simplificar el versionado visible.

## Reglas
- Cada rol estructural del tema aplicado usa exactamente el hexadecimal definido en su perfil.
- No se mezclan los colores del nuevo tema con el azul CorePulse anterior.
- `theme_color(theme_color(x))` debe producir el mismo color que una sola aplicación.
- Se mantienen los 10 temas.
- Runtime universal canónico preservado byte por byte.
- Versionado visible simple desde V100.

## Estado
PASS
