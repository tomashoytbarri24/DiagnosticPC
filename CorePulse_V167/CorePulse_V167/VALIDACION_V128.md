# VALIDACIÓN V128

## Objetivo
Eliminar definitivamente la diferencia visual entre la previsualización de Temas y la interfaz aplicada, evitando roles inferidos, grises por defecto de CustomTkinter y superficies grandes más oscuras que las mostradas en la vista previa.

## Cambios
- Dashboard: `bg`, `sidebar`, `surface`, `surface_2`, `border`, textos y acentos usan `role_color()` directamente.
- Navegación activa: usa `accent_2` + hover `accent` + texto `text`, igual que el mock de Temas.
- Gráficos y almacenamiento: las superficies visuales amplias usan `surface_2` exacto.
- Startup Gate: usa `surface_2` exacto y track `border`; no deriva un fondo oscuro.
- Primer frame de `main.py`: nace con roles exactos para evitar flashes/estados previos antes del polish.
- Galería de Temas: el área scroll, shells, mock, tarjetas y gráfico reciben colores explícitos desde su creación. Se elimina el gris por defecto de CTk en el scroll.
- Botones/badges del selector usan `text` de la paleta, no `#ffffff` externo.

## Validaciones
- PASS — V128 / `EXACT_THEME_ROLE_PARITY`.
- PASS — los 10 temas devuelven exactamente el hexadecimal declarado en cada rol.
- PASS — `preview_color()` y `role_color()` coinciden 1:1 con la paleta.
- PASS — Dashboard / layout / navegación comparten el mismo contrato semántico.
- PASS — Startup Gate y superficies amplias usan `surface_2` exacto.
- PASS — el selector no deja superficies estructurales al color por defecto de CustomTkinter.
- PASS — runtime canónico y SMART/NVMe sin cambios.

## Política
No se generan colores intermedios para las superficies cubiertas por este contrato: no hay `darken`, `lighten`, mezcla ni filtro. Los colores semánticos de estado (verde/ámbar/rojo/púrpura) se conservan cuando representan información funcional, no decoración de tema.
