# CorePulse V130 — Validación

## Objetivos
- Temas visible con fondo de paleta desde el arranque, sin depender de un primer clic.
- Actualizaciones integrada en la ventana principal mediante `internal_navigation`.
- Sin `CTkToplevel` para el Centro de actualizaciones.
- Flujo de búsqueda/descarga/verificación/instalación/rollback conservado.
- Runtime canónico y SMART/NVMe sin cambios.

## Criterios
- `dashboard_layout.py` excluye Temas del estilo transparente genérico y reafirma su `accent` al final de cada reflow.
- `internal_navigation.py` registra `updates` como página cacheable.
- `main.py::open_update_center()` usa `activate_internal_page` + `commit_internal_page`.
- `UpdatePanel` se construye dentro del host y no crea otra ventana.
- La página realiza una comprobación automática y conserva botón de refresco manual.
