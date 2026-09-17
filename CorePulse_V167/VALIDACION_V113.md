# VALIDACIÓN V113 — Benchmark configurable antes de ejecutar

## Objetivo
Evitar que el usuario pueda iniciar un benchmark antes de revisar/configurar su perfil y componentes.

## Reglas
- Estabilidad no ejecuta el benchmark directamente; abre la configuración.
- El orden visual es: perfil → componentes → resumen de selección → ejecutar.
- Ejecutar queda deshabilitado sin componentes.
- Perfil y componentes quedan bloqueados durante una ejecución.
- Runtime universal y salud de discos no se modifican.

## Estado
PASS
