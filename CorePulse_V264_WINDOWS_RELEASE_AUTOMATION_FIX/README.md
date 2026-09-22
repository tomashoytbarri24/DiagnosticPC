# CorePulse V264 — Release Automation Fix

V264 parte de V263 sin cambiar Benchmark, Driver Hub, telemetría, salud, temas ni el flujo Git de publicación. Esta revisión corrige la infraestructura de GitHub Actions/Releases que seguía seleccionando carpetas antiguas con nombres cortos como `CorePulse_V182`.

## Cambios V264

- Plantillas Development y Stable actualizadas al esquema **V2 long-folder**.
- Detectan la carpeta `CorePulse_V###_...` realmente modificada en el push.
- Validan el número de carpeta contra `core/version.py`.
- Empaquetan `CorePulse_V###.zip` + `CorePulse_V###.zip.sha256`.
- Desarrollo publica/actualiza `V###-dev`; `main` publica `V###` estable.
- El workflow estable no reemplaza una Release estable existente.
- Ejecución manual (`workflow_dispatch`) permite reconstruir una Release indicando la carpeta.
- CorePulse detecta Actions legacy y avisa que deben actualizarse, sin modificar `.github`.
- Se fijó el runner a `ubuntu-24.04` y Actions V7.

> Las plantillas viven en `developer/github_actions_templates/`. Para que GitHub las use hay que instalarlas una vez en `.github/workflows` del repositorio.
