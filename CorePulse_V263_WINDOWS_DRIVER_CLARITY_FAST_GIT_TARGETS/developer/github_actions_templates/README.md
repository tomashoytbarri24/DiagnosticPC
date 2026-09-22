# GitHub Actions — plantillas V262

Estas plantillas NO se instalan ni modifican `.github` desde CorePulse.

La idea es mantener los workflows del repositorio como autoridad de Releases:

- `corepulse-development-release.yml`: ramas `**/corepulse-dev` -> `V###-dev` prerelease.
- `corepulse-stable-release.yml`: `main` -> `V###` release estable.

El publicador de CorePulse sólo elige la rama y sube la carpeta de la versión. Para activar estas plantillas, el propietario del repositorio debe copiarlas una sola vez a `.github/workflows/` en el repositorio raíz.
