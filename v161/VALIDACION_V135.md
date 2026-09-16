# Validación V135

- Versión centralizada: V135 / `SAFE_GIT_PUBLICATION_WITH_COMMIT_MESSAGE`.
- Centro de Actualizaciones incorpora `Publicar versión` dentro de la misma ventana.
- Permite escribir un mensaje de commit libre antes de publicar.
- Bloquea `main`, `master`, `trunk` y detached HEAD.
- Exige que `FASE 1`, `FASE 2` y `FASE 3` existan en el repositorio.
- El staging/commit sólo admite carpetas `CorePulse_Vxxx`; si existen cambios preparados fuera de ese ámbito la publicación se bloquea.
- Usa autenticación Git ya configurada; no persiste tokens/contraseñas.
- Tras el push genera `CorePulse_V135.zip` y su sidecar SHA-256 para una futura GitHub Release.
- Si falla antes del commit, revierte únicamente la preparación CorePulse.
- Runtime canónico y SMART/NVMe no cambian.
