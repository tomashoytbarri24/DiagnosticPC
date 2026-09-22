# Validación V181 — Safety propagation + UI settle

V181 deriva de V180 y conserva el workload visual V13.

Validaciones automáticas:

```powershell
python -m unittest tests.test_v177_benchmark_ui tests.test_v178_benchmark_v13 tests.test_v179_thermal_ui_closure tests.test_v180_safety_ui_atomic tests.test_v181_safety_propagation_ui_settle -v
```

Criterios manuales:

- 97 % debe seguir mostrando `EN EJECUCIÓN`.
- Al 100 %, `ÚLTIMO RESULTADO` debe aparecer completo.
- Al desplazarse inmediatamente por los resultados no deben quedar textos duplicados ni restos del frame anterior.
- Si `Gatillo CPU real` muestra racha 3/3 o mayor, el suite debe finalizar `SAFETY_STOP`.
- Si sólo existe un mínimo de 0.0/1.0 °C pero la racha es menor que 3, no se debe afirmar que el gatillo fue sostenido.
