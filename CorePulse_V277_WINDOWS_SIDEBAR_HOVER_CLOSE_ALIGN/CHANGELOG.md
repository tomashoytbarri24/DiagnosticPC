## V277
- Base V276.
- Reacomodado el bloque superior del sidebar.
- La X de cierre deja de quedar fija a la izquierda: ahora aparece arriba a la derecha solo cuando el mouse entra al sidebar.
- Ajustado el espaciado superior para que la cabecera del sidebar quede limpia y mejor alineada.
- Sin cambios funcionales en navegación, telemetría, diagnóstico, benchmark, SMART o REAL_OR_NA.

## V276
- Base V275.
- Corregido el criterio que empujaba Personalización al fondo del sidebar en alturas normales.
- El bloque Personalización solo se ancla abajo en ventanas realmente bajas; en tamaños normales queda inmediatamente después de Historial.
- Sin cambios funcionales en navegación, telemetría, diagnóstico, benchmark, SMART o REAL_OR_NA.

## V275
- Base V274.
- Corregida la composición visual de la parte baja del sidebar.
- Personalización deja de quedar flotando en ventanas con alto normal: ahora fluye justo después de Historial y solo se ancla abajo en layouts realmente ajustados.
- Ajustados márgenes del bloque inferior y de la versión para un cierre más limpio.
- Sin cambios funcionales en navegación, telemetría, diagnóstico, benchmark, SMART o REAL_OR_NA.

## V274
- Base V273.
- Ajustado el borde inferior del sidebar para que quede anclado al borde real inferior del panel, sin verse desplazado ni hacia adentro.
- Reducido levemente el margen inferior del bloque Personalización para que el cierre visual inferior del sidebar se vea limpio y continuo.
- Sin cambios funcionales en navegación, telemetría, diagnóstico, benchmark, SMART o REAL_OR_NA.

## V273
- Base V272.
- Corregido el borde del sidebar: los cuatro lados ya no quedan 8 px hacia adentro; ahora siguen el perímetro real del panel.
- Se conserva el borde estructural neutro y los separadores internos neutros de V272.
- Sin cambios funcionales en navegación, telemetría, diagnóstico, benchmark, SMART o REAL_OR_NA.

## V272
- Base V271.
- Borde exterior del sidebar reconstruido con cuatro líneas nativas de 2 px para mejorar definición y continuidad visual.
- Separadores internos cambiados de celeste a borde estructural neutro del tema.
- Sin cambios funcionales en navegación, telemetría, diagnóstico, benchmark, SMART o REAL_OR_NA.

## V271
- Base V269.
- Borde exterior corregido sin cambiar el fondo del sidebar.
- Separadores horizontales en celeste CorePulse.

## V268
- Igualado el ancho visual de Supervisión actual con Salud del sistema.

## V267
- Borde exterior del sidebar reforzado para que el rectángulo sea claramente visible.

## V266
- Borde del sidebar continuo.
- Separadores horizontales visibles.
- Actualizaciones permanece visible.

## V265
- Reparación visual del borde del sidebar y divisores horizontales.
- Se conserva Actualizaciones visible en el footer.

## V264
- Restaurados separadores horizontales visibles del sidebar.
- Corregido el recorte de Actualizaciones en Personalización.
- Ajustado espaciado vertical sin alterar navegación ni lógica funcional.

## V263
- Sidebar completo convertido en panel rectangular integrado.
- Sin cuadro interno: todos los controles siguen siendo hijos del sidebar original.
- Añadidos borde exterior y separadores visuales.
- Basado en V259 para evitar regresiones de V260/V262.

## V259
- Tarjeta de inicio con bordes cuadrados.
- Se elimina el porcentaje del splash; queda sólo la barra de progreso real.

# CorePulse Changelog — rama actual

## V257
- Limpieza estructural del proyecto sobre V256.
- Eliminados `__pycache__`, `.pyc`, `.pytest_cache`, logs/resultados vacíos y documentación de validaciones históricas.
- Eliminados runners GPU versionados antiguos de `tools/` y raíz.
- Eliminado bootstrap fuente obsoleto y helpers físicos no usados por el runtime actual.
- Eliminado `core/visual_benchmark.py`, sin imports desde la ruta vigente DirectX.
- Conservados código funcional, assets, PresentMon, build/installer y contratos REAL_OR_NA.

## V256
- Eliminación de textos secundarios marcados por el usuario.

## V255
- Corrección de `padx` inválido en CTkButton.

## V254
- Refinamiento visual del sidebar.

## V253
- Paridad de posición del control de sidebar.

## V252
- Controles de sidebar con iconos simples.
