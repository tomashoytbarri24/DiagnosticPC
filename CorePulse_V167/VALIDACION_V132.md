# Validación V132

## Objetivo
Corregir el fallo de arranque de V131 provocado por `padx` pasado al constructor de `customtkinter.CTkButton`.

## Comprobaciones
- `gui/dashboard.py` ya no pasa `padx` ni `pady` a ningún `CTkButton`.
- Temas y Actualizaciones conservan el bloque de Personalización de V131.
- La versión centralizada es V132 / `CTK_BUTTON_PADDING_STARTUP_FIX`.
- `compileall` del proyecto completo finaliza correctamente.
- Runtime canónico y SMART/NVMe conservan sus hashes.
