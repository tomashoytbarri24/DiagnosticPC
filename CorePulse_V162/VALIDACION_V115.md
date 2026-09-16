# Validación V115 — Reportes AppData

## Objetivo
Mantener el PDF de Diagnóstico en una ruta persistente de CorePulse bajo AppData y evitar generación/apertura inesperada.

## Reglas verificadas
- `Generar PDF` usa `diagnostics_dir()` y no abre selector de carpetas.
- Entrar a Diagnóstico no dispara `export_pdf_report()` automáticamente.
- `Abrir último PDF` sigue disponible sólo cuando existe un PDF real.
- `Abrir carpeta de informes` abre la carpeta fija aunque todavía no haya PDF.
- El último PDF puede recuperarse desde `last_pdf_report.txt` o buscando el informe más reciente en AppData.
- No se modifica salud SMART/NVMe ni el runtime universal canónico.

- Diagnóstico muestra un acceso directo `Sensores y compatibilidad` a la trazabilidad de telemetría.
