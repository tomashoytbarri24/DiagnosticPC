# Validación V180 — Safety + Atomic UI

## Alcance

V180 deriva de V179 y no cambia el motor DirectX ni el workload V13.

## Pruebas automáticas

```text
python -m unittest tests.test_v177_benchmark_ui tests.test_v178_benchmark_v13 tests.test_v179_thermal_ui_closure tests.test_v180_safety_ui_atomic -v
```

Resultado esperado: **18/18 PASS**.

## Protección CPU

- 3 muestras consecutivas con distancia real a TjMax `<= 1,0 °C` => `SAFETY_STOP`.
- Una muestra por encima de `1,0 °C` reinicia el contador sostenido.
- Sin distancia real a TjMax no se deduce ni se fija un TjMax universal.

## UI

- `visual_benchmark` no solicita el render completo del Canvas al terminar normalmente.
- Los resultados se preparan en staging y se muestran en un único swap.
- Existe fallback a render completo sólo si el host dejó de existir, por ejemplo al cambiar de vista durante la ejecución.
