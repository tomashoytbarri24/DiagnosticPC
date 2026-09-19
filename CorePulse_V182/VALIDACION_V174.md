# Validación CorePulse V174

## Alcance
- Idempotencia visual de Ajustes Linux.
- Feedback inmediato al cambiar perfil energético.
- Ampliación y coherencia de temas claros.

## Resultado automatizado
- Quality Gate: PASS.
- 192 pruebas correctas.
- 15 omitidas por depender de GUI/display no disponible en el entorno de validación.
- 180 snapshots históricos fuera del gate actual.
- 11 subpruebas correctas.

## Validación física recomendada en Linux
1. Abrir Ajustes Linux y pulsar Actualizar varias veces: cada sección debe aparecer una sola vez.
2. Cambiar entre Ahorro, Equilibrado y Rendimiento: la selección visual debe cambiar inmediatamente.
3. Abrir Temas > Claros: deben aparecer 6 opciones y la vista previa debe pertenecer siempre al filtro activo.
