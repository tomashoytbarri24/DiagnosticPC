# VALIDACIÓN V309 — SIDEBAR ASYNC DRAWER

## Problemas observados en V308
- Sensación de latencia al alternar el sidebar.
- Un frame intermedio podía mostrar textos/tarjetas duplicados durante el commit.

## Estrategia V309
- El sidebar se desliza durante ~96 ms como drawer superpuesto.
- El ancho del dashboard permanece fijo durante todo el slide.
- Al finalizar se hace un único cambio de grid con WM_SETREDRAW.
- WM_SETREDRAW se aplica a un único HWND raíz.
- El reflow de Matplotlib se difiere 24 ms y usa draw_idle.
- No hay `_apply_layout`, `canvas.draw()` ni `update_idletasks()` por frame.

## Integridad
- Sin cambios en telemetría, REAL_OR_NA, REAL_FPS_OR_NA_ONLY ni sensores.
