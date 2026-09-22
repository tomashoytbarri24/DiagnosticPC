# V226 — Sidebar Runtime NameError Fix

## Errores corregidos
- `PRIMARY` no estaba definido en `_style_header_mode()`; se reemplaza por `CYAN`, que es el acento real ya definido en el módulo.
- `compact` se usaba dentro de `_style_sidebar()` fuera de su alcance; se reemplaza por un tamaño estático válido para los botones de Personalización.

## Validación adicional
Además de `py_compile`, V226 incluye una comprobación estática de símbolos globales usados por `dashboard_layout.py` para detectar referencias no definidas que Python no descubre hasta tiempo de ejecución.

## Política
- Mantiene el sidebar fijo de V224.
- Mantiene la tipografía/iconos ampliados de V225.
- Mantiene REAL_OR_NA / REAL_FPS_OR_NA_ONLY.
