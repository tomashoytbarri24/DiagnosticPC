# V236 — Resource Status Card Runtime Stability

## Objetivo
Reparar el fallo de arranque introducido en V235 sin añadir cambios visuales adicionales.

## Corrección
- Se declara `ICON_FONT = "Segoe UI Symbol"` en `gui/dashboard.py`, requerido por los iconos de las nuevas tarjetas CPU/RAM/GPU y almacenamiento.
- Se añade validación estática de globals no definidos en `dashboard.py` y `dashboard_layout.py`.
- Se valida que las funciones críticas de arranque (`_rebuild_sidebar`, `_rebuild_main_layout`, `_style_existing_cards`) sigan presentes.

## Política
- Se conserva la estructura visual V235.
- No cambia telemetría, diagnóstico ni REAL_OR_NA.
