# Validación V264

- Plantillas V2 aceptan nombres largos `CorePulse_V###_...`.
- El detector valida `core/version.py`.
- Los assets se publican como `CorePulse_V###.zip` y sidecar SHA-256.
- Development permite actualizar prerelease del mismo tag.
- Stable rechaza sobrescribir una release estable existente.
- CorePulse no modifica `.github`; sólo diagnostica si el workflow local es legacy.
