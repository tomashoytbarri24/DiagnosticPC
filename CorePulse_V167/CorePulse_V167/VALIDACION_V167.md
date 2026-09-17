# Validación V167

Objetivo: automatizar la prerelease del canal Desarrollo en cada push a `*/corepulse-dev` sin alterar los perfiles Git ni el actualizador seguro V166.

- Versionado central actualizado a V167.
- Workflow GitHub Actions administrado desde el publicador por perfiles.
- Una prerelease por versión (`V167-dev`), actualizada en pushes posteriores de la misma versión.
- ZIP limpio y SHA-256 generados automáticamente.
- El canal Desarrollo consume la prerelease; Estable la ignora.
- Sin credenciales personales hardcodeadas en el workflow.
