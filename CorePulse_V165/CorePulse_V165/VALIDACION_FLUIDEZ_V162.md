# V162 — optimización de interfaz, 17 de septiembre de 2026

Cambios aplicados directamente en esta carpeta; se mantiene V162.

## Tercera ronda — cola de trabajo durante scroll

El scroll acumulaba callbacks y, al quedar quieto, ejecutaba sólo el último. Eso podía descartar una finalización de detección de Tweaks si después llegaba una solicitud de filtro. Ahora las tareas independientes se conservan; sólo se reemplazan las solicitudes que declaran explícitamente la misma clave de repintado.

Alertas, historial, tendencias, Centro de salud y filtros de Tweaks usan claves de agrupación. La finalización de detección conserva su llamada sin clave y no se pierde. Un scroll prolongado ya no retiene cientos de copias de los datos de un mismo repintado.

Se añade `tests.test_scroll_deferred_work` al comando acumulado. **123 pruebas: 122 aprobadas, 1 omitida, 0 fallos**. Las siete pruebas nuevas cubren 1.000 repintados agrupados en uno, finalizaciones y filtros juntos, continuidad del scroll, callbacks que fallan, tareas añadidas durante la ejecución y destrucción del host. Son pruebas de comportamiento con un scheduler controlado; no una medición de FPS del escritorio.

Comprobación manual: en Tweaks, iniciar la detección de estado, desplazar la lista y cambiar un filtro antes de terminar; al dejar de desplazar, comprobar que aparece el resultado y que la vista responde. También revisar alertas e historial tras desplazarse durante varias actualizaciones.

## Segunda ronda — Gaming y páginas ocultas

- Corregidas las cifras de la portada Gaming que quedaban congeladas cuando no cambiaba la generación del perfil. FPS/CPU/GPU/RAM ahora refrescan sus controles existentes usando la misma fuente y formato del primer dibujo. Las cifras repetidas no se vuelven a escribir.
- Los trabajos que terminan con una página oculta conservan una marca de actualización pendiente. Al volver se solicita un único render; ocultar la página cancela su render programado.
- Un callback de una pestaña anterior ya no reconstruye la vista Audio ni pierde las peticiones de la nueva pestaña.
- Pulsar la sección de Gaming que ya está abierta conserva sus widgets; cambiar de sección sí construye la vista correspondiente.
- Al iniciar un cambio de perfil se muestra el estado ocupado antes de finalizar el trabajo. Se retiró una consulta de estado cuyo resultado no se utilizaba.

Validación acumulada tras esta ronda: **116 pruebas: 115 aprobadas, 1 omitida, 0 fallos**. Se añade `tests.test_health_panel_refresh_lifecycle` al comando principal indicado abajo. Las once pruebas nuevas ejercitan los métodos reales con widgets y un scheduler controlados, incluyendo finalización de un worker real mientras la página está oculta. No reproducen el escritorio ni sustituyen la comprobación visual.

Comprobación adicional recomendada: permanecer unos segundos en Inicio de Gaming para ver las cifras cambiar; iniciar una consulta de Centro de salud, salir antes de que termine y volver para comprobar que presenta el resultado.

## Cambios

- Las etiquetas y barras del monitoreo sólo reciben escrituras cuando cambia su valor. Se consulta el widget actual, de modo que cambios de tema o escrituras desde otras vistas no quedan ocultos por una caché.
- Se evitan pinturas intermedias de títulos CPU/GPU y del estado de salud cuando los enlaces del dashboard ya son responsables del resultado final. Los cálculos y las alertas se conservan.
- El estado de Game Boost devuelve la última instantánea completa cuando una operación tiene ocupado su bloqueo; la consulta de la interfaz no espera a que termine esa operación.
- El temporizador de gráficos conserva su cadencia de comprobación, pero actualiza series sólo cuando llega una muestra nueva. No dibuja desde ese temporizador mientras se muestra una página interna, la ventana está oculta/minimizada o se está redimensionando. La adquisición y el historial continúan.
- Los ejes temporales se actualizan sólo cuando cambian. En ese caso se regenera el fondo de Matplotlib para incluir las nuevas etiquetas; también se recupera tras una invalidación por tamaño.
- El estado del Overlay omite escrituras de texto/colores idénticos.
- Se retiran 42 líneas del antiguo refresco duplicado de Gaming: una función vacía, su temporizador sin punto de arranque y sus referencias internas. El panel hijo conserva su propio refresco y ciclo de activación.

No se borraron documentos, pruebas históricas, datos del usuario, motores de diagnóstico ni archivos por su nombre o antigüedad.

## Validación

Comando principal:

```powershell
python -m unittest tests.test_chart_render_efficiency tests.test_ui_update_efficiency tests.test_v162_balanced_audio_responsiveness tests.test_audio_navigation tests.test_managed_power_plans tests.test_power_reconciliation tests.test_audio_test tests.test_v159_resize_ownership -q
```

Resultado: **105 pruebas: 104 aprobadas, 1 omitida, 0 fallos**.

- Matplotlib con backend Agg: 100 ticks sin muestras nuevas producen un solo dibujo inicial; una muestra nueva sí actualiza la serie. Se comprueban retorno desde vista oculta, redimensionado, etiquetas temporales, N/A y recuperación de un fallo de dibujo.
- Widgets instrumentados: las muestras repetidas no generan nuevas escrituras; cambios reales y cambios externos de tema sí se aplican.
- Pruebas adicionales aprobadas: autoridad de alertas críticas (`test_unified_live_health_agent_instant.py`), restauración de Game Boost (16 comprobaciones) e historial de gráficos (7 comprobaciones).
- `test_startup_responsiveness_single_layout_authority.py` no pasa su primera comprobación: exige literalmente la versión 103 y el proyecto es V162. Ese supuesto ya estaba obsoleto antes de estos cambios; no se alteró para presentar un resultado favorable.
- Sintaxis de los archivos Python modificados y hashes SHA-256 de los cinco archivos protegidos revisados al cierre.

Los recuentos anteriores miden operaciones de dibujo en pruebas, no una mejora porcentual de velocidad del programa completo. Las pruebas de energía usan respuestas simuladas y no cambian los planes físicos del equipo.

## Límites

La prueba gráfica de audio se omite porque Tcl/Tk no dispone de un `init.tcl` utilizable en el entorno de pruebas. No se validó el arrastre/maximizado real de la GUI ni se reprodujo o grabó audio físico. Por tanto, no se afirma que el parpadeo de Windows esté totalmente resuelto.

Durante la preparación de la prueba de telemetría se detectó que importar el módulo real inicializaba sensores y podía fallar en Python.Runtime al cerrar ese proceso de prueba. El test final aísla ese módulo y ejecuta el método real de presentación con datos controlados; no se atribuye ese resultado a una corrección del motor de sensores.

## Comprobación manual

1. Cerrar y volver a iniciar CorePulse desde esta carpeta.
2. Revisar que CPU/RAM/GPU cambian en el Resumen y sus gráficos siguen avanzando.
3. Abrir Gaming o Centro de salud, esperar unos segundos y volver al Resumen.
4. Maximizar/restaurar y arrastrar los bordes; comprobar textos y gráficos.
5. Abrir Test de Audio y comprobar su navegación integrada y sus controles.
6. Revisar Overlay y los perfiles de rendimiento.

## Próximas mejoras propuestas

- Medir latencia del hilo gráfico, tiempo de apertura por página y coste de cada consulta, además de los tiempos de arranque existentes. Esto permitiría localizar las pausas que queden en este equipo.
- Actualizar tarjetas de Gaming/Centro de salud en el sitio cuando cambia su estado, en vez de reconstruir una página completa en cambios de generación.
- Consolidar gradualmente las capas históricas de presentación del dashboard bajo un único responsable, con pruebas de navegación y temas antes de retirar cada compatibilidad.
- Añadir una vista opcional de rendimiento de CorePulse (uso propio, consultas lentas y edad de los datos), sin alterar las métricas del hardware.
- Separar pruebas históricas ligadas a versiones antiguas de las regresiones vigentes, conservando sus comprobaciones útiles.
