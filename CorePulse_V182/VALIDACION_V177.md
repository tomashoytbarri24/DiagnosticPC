# Validación V177

Objetivo: limpiar la presentación del Diagnóstico sin inventar datos.

- REAL_OR_NA permanece en el modelo.
- Facetas sin valor real no se dibujan.
- NO_EVALUABLE con datos parciales se presenta como PARCIAL; sin datos, SIN DATOS.
- Ver evidencia sólo se ofrece cuando build_component_evidence contiene filas reales.
- El panel de evidencia nunca abre una tarjeta vacía.
- Windows/Linux comparten la misma regla de presentación.

El reemplazo del benchmark 3D queda fuera de V177 para no mezclar un cambio de motor gráfico con el cierre del diagnóstico.
