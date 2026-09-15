# Validación V0.10.2.92w — Battery Wear State Visual Refinement

- `compileall`: PASS.
- `test_battery_summary_visual_parity.py`: 14/14 PASS.
- `test_battery_wear_state_visual.py`: 12/12 PASS.
- `test_battery_current_desktop_aware.py`: 15/15 PASS.
- Regresión seleccionada: 28/28 suites PASS.
- Desgaste usa tarjeta vertical dedicada con `rowspan=2`.
- No existe `CTkProgressBar` ni barra decorativa dentro de la tarjeta de desgaste.
- `N/A` conserva tono neutro.
- El porcentaje real no se modifica; el color es únicamente contextual.
- No se modifican sensores, fuentes de batería, `REAL_OR_NA`, Gaming, Windows, Safe Storage Scanner, RAM reclaim, perfiles de energía ni rollback.

La apariencia final bajo DPI/escala de Windows requiere validación visual en Windows.
