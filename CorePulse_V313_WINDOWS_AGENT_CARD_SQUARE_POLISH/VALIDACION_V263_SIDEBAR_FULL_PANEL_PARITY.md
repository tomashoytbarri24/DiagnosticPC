# V263 — Sidebar Full Panel Parity

Base: V259.

- No se usa `place()` para crear un panel interno.
- No se reparentan widgets Tk/CustomTkinter.
- El `app.sidebar` original recibe borde de 1 px, `corner_radius=0` y margen exterior.
- Los botones funcionales originales permanecen hijos directos de `app.sidebar`.
- Separadores de 1 px agrupan las secciones.
- El colapso/reapertura mantiene los mismos márgenes al reconstruir el grid.
