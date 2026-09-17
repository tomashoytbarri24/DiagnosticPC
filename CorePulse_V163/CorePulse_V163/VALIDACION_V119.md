# VALIDACIÓN V119 — Recuperación ante cierres no limpios

- Marcador de sesión persistente en AppData con PID + create time + heartbeat.
- Un cierre normal elimina el marcador sólo después de rollbacks y verificación final de energía.
- Un cierre brusco deja evidencia para el siguiente inicio.
- Game Boost conserva su rollback persistente existente y V119 registra el resultado de recuperación.
- Prioridad de proceso y Power Throttling de juegos también guardan rollback persistente; al reiniciar sólo se restauran si el PID/create-time y el valor aplicado siguen coincidiendo, para no pisar cambios externos.
- Tweaks persistentes elegidos por el usuario NO se revierten automáticamente.
- Historial local limitado de cierres limpios/no limpios para diagnóstico.
- Cada cierre no limpio genera un reporte técnico JSON local en AppData\CorePulse\diagnostics\crash_reports.
