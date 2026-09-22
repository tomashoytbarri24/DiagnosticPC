# VALIDACIÓN V121 — Startup Analyzer seguro

- Inventario de HKCU/HKLM Run/RunOnce + carpetas Startup + Win32_StartupCommand.
- Muestra fabricante cuando el ejecutable expone CompanyName, ubicación, estado, RAM actual e impacto observado.
- Integra Diagnostics-Performance Event 101 como evidencia de degradación real.
- Sólo permite deshabilitar entradas de usuario reversibles (HKCU y Startup del usuario).
- HKLM, Microsoft, seguridad, sistema y orígenes sin rollback exacto son sólo observación.
- Cada deshabilitación guarda copia exacta en AppData y puede restaurarse.
- Restaurar nunca sobrescribe una entrada recreada externamente.
- Política: ninguna deshabilitación automática.
