# V213 — Collapsible Sidebar Startup Fix

## Error corregido
V212 podía detener el arranque con `NameError: _style_existing_cards is not defined`.

La causa fue una sustitución demasiado amplia al reconstruir `_rebuild_sidebar()`, que eliminó cinco helpers del dashboard situados entre `_rebuild_sidebar()` y `_rebuild_main_layout()`.

## Restaurado
- `_style_existing_cards()`
- `_series_stats()`
- `_update_trend_titles()`
- `_apply_chart_geometry_alignment()`
- `_style_charts()`

## Conservado
- Sidebar colapsable/expandible.
- Reacomodo del contenido principal.
- Animación corta con estela tipo motion blur.
- REAL_OR_NA sin cambios.
