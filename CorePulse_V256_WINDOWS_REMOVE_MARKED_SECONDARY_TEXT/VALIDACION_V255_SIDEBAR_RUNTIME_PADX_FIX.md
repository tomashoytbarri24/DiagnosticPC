# VALIDACIÓN V255 — Sidebar runtime padx fix

Base: V254.

Corrección puntual de arranque:
- Se eliminó `padx` de los constructores `CTkButton` de **Temas** y **Actualizaciones**.
- `CustomTkinter.CTkButton` no admite `padx` como argumento del constructor en el runtime Windows usado por CorePulse.
- El espaciado exterior sigue controlado por `.pack(..., padx=...)`, que sí es válido.
- No se modifica telemetría, sensores, SMART, benchmark, gráficos, Centro de salud ni REAL_OR_NA.
