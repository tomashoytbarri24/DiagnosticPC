# Validación V156

Objetivo: pulido general seguro de CorePulse sin tocar el publicador, el resize pendiente, SMART/NVMe ni el runtime canónico.

## Cambios
- Controladores: `OLD` ahora se presenta como **Antiguo · revisar actualización**. La interfaz explica que la antigüedad NO confirma que exista un driver nuevo.
- Controladores: se muestra **Edad aprox.** junto a proveedor, versión y estado.
- La sección antes llamada **Alertas y diagnóstico** pasa a **Alertas técnicas** para no confundirse con el Diagnóstico Completo.
- Benchmark/Historial: aumento moderado de tipografía en textos de 6–8 px que resultaban demasiado pequeños.
- Dashboard: mejora de legibilidad en microetiquetas sin alterar la geometría estructural.
- Limpieza: footer menos redundante y badges más legibles.

## Límites
- No se implementa búsqueda/descarga/instalación online de drivers en V156.
- No se modifica Publicar/Actualizaciones.
- No se modifica la optimización de resize pendiente.
- `REAL_OR_NA` se mantiene.
