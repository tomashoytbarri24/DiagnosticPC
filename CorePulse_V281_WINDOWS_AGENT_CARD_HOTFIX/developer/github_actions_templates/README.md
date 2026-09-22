# GitHub Actions de CorePulse — esquema V2

Estas plantillas corrigen la automatización de Releases para carpetas con nombres largos como `CorePulse_V264_WINDOWS_...`.

## Qué cambia

- El Action de desarrollo detecta **la carpeta CorePulse modificada por el push**, no la versión antigua con nombre corto más alto.
- Valida que `CorePulse_V###_...` y `core/version.py` indiquen el mismo número.
- Si un push modifica más de una versión, falla en vez de empaquetar una versión incorrecta.
- `workflow_dispatch` permite indicar una carpeta manualmente; si se deja vacío usa la versión válida más alta.
- El ZIP sigue llamándose `CorePulse_V###.zip`, compatible con el actualizador de CorePulse.
- Desarrollo crea/actualiza `V###-dev`; main crea una Release estable `V###` y no sobrescribe una estable existente.
- Se usan `actions/checkout@v7`, `actions/setup-python@v7` y `ubuntu-24.04`.

## Instalación

Estos archivos pertenecen al **repositorio DiagnosticPC**, no a una carpeta de versión. Copia los YAML a `.github/workflows/`.

CorePulse no modifica `.github` automáticamente. Para que ambos canales funcionen, los workflows deben existir en las ramas donde se disparan: desarrollo en `*/corepulse-dev` y estable en `main`.
