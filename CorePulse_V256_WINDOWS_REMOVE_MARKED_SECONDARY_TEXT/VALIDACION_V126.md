# VALIDACIÓN V126

## Objetivo
Validar el rediseño solicitado para Centro de salud > Windows y reforzar la visibilidad de Temas sin alterar runtime universal ni SMART/NVMe.

## Comprobaciones
- PASS — versión `126` y stage `WINDOWS_HEALTH_SUMMARY_CARDS_THEME_CTA`.
- PASS — portada Windows en tarjetas grandes 2×2: Inicio, Servicios, Estabilidad y Controladores.
- PASS — cada tarjeta ejecuta/actualiza su análisis desde la portada.
- PASS — `Ver más` permanece deshabilitado hasta contar con un resultado real y abre la vista detallada existente.
- PASS — cantidad analizada procede del payload real de cada analizador.
- PASS — Inicio/Servicios muestran el elemento más pesado sólo si existe memoria RAM medida; sin dato se conserva `N/A`.
- PASS — Estabilidad/Controladores muestran el elemento más relevante usando únicamente clasificaciones/eventos ya observados.
- PASS — Inicio deja de limitar la vista a 18 filas y permite recorrer todos los elementos mediante paginación.
- PASS — Servicios, Estabilidad y Controladores conservan sus tablas/paginación previas.
- PASS — botón `TEMAS` aumenta a 42 px, borde 2 px y permanece con `accent`/`accent_2` exactos incluso tras refrescar la navegación.
- PASS — etiqueta `PERSONALIZACIÓN` se mantiene junto al CTA de Temas después de montar la tarjeta del agente.
- PASS — `compileall` completo.
- PASS — runtime canónico y SMART/NVMe conservan exactamente los hashes de V125.

## Política
`REAL_OR_NA`, `REAL_FPS_OR_NA_ONLY` y la filosofía de merge acumulativo permanecen intactas.
