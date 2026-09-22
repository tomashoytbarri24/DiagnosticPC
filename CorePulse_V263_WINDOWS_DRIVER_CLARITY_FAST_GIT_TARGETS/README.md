# CorePulse V263 — Driver Clarity & Fast Git Targets

V263 parte de V262 y mantiene su publicación segura, benchmark, salud NVMe, temas, audio y scroll. Esta revisión aclara el diagnóstico de controladores y elimina la pausa perceptible al cambiar entre `main` y la rama de desarrollo.

## Cambios de V263

- `Problemas` pasa a **Incidencias** y ya no vuelve a contar los controladores sin firma.
- Las incidencias muestran el `ConfigManagerErrorCode` real de Windows y una explicación corta cuando existe.
- `Sin firma` permanece como señal separada; no se interpreta automáticamente como malware ni como fallo.
- `Antiguo` sólo se usa como señal accionable para hardware relevante de terceros; componentes virtuales/inbox de Microsoft quedan fuera de esa alerta.
- Driver Hub prioriza incidencias, paquetes antiguos de terceros y hardware físico relevante antes de consultar el catálogo.
- Cambiar destino Git (`main`, `*/corepulse-dev`, otra rama) reutiliza el análisis cacheado y actualiza la UI al instante; `Analizar cambios` y `Publicar` siguen revalidando origin.
- FASE 1/2/3, `.github`, versiones anteriores, HEAD y staging local continúan protegidos.
