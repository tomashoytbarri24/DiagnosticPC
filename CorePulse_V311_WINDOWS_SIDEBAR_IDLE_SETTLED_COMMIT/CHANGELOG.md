## V311
- Base V310.
- Sidebar: el commit final ya no reactiva el dibujo de Windows inmediatamente después del cambio de grid.
- El HWND raíz permanece congelado un ciclo idle adicional para que CustomTkinter termine sus redibujos internos antes de publicar el frame final.
- Se elimina el frame fantasma con textos/tarjetas duplicadas observado al finalizar la apertura/cierre.
- Se conserva el drawer rápido de V310 y el reflow de Matplotlib sigue siendo asíncrono.

## V310
- Base V309, conservando su comportamiento visual estable.
- Sidebar: transición reducida de 96 ms a 72 ms y de 8 a 6 pasos para mejorar respuesta percibida.
- Se evita llamar lift() en cada frame de la animación; el sidebar se eleva una sola vez al iniciar.
- Reflujo de gráficos posterior al commit reducido de 24 ms a 8 ms y sigue usando draw_idle.
- Sin cambios en telemetría, REAL_OR_NA, REAL_FPS_OR_NA_ONLY ni lógica funcional.

## V309
- Base V308.
- Sidebar: nuevo drawer asíncrono. Durante el deslizamiento sólo se mueve el sidebar; el dashboard no cambia de ancho por frame.
- El cambio de ancho del contenido ocurre una sola vez al final bajo un commit Win32 corto.
- Se elimina `_apply_layout()` de la ruta crítica del clic y Matplotlib se refluye 24 ms después del commit.
- Se usa un único HWND raíz para WM_SETREDRAW, evitando el frame fantasma/duplicado observado en V308.
- Se soporta un segundo clic rápido mediante cola de estado, sin reentrancia de geometría.

## V308
- Base estable V306; se descarta el slide geométrico de V307 porque reintroducía estados intermedios visibles.
- Sidebar: transición atómica más rápida usando WM_SETREDRAW sin mover el sidebar real con place().
- Se elimina el canvas.draw() síncrono del gesto de abrir/cerrar; Matplotlib se redibuja con draw_idle después del commit final.
- El layout deja de forzarse completo durante el toggle y usa el fast-path cuando el breakpoint no cambia.
- Se conserva Windows-only, multi-Python, frecuencia CPU universal y REAL_OR_NA.

## V306
- Base V305.
- Sidebar: se elimina la transición por captura/snapshot y cualquier efecto visual artificial al abrir/cerrar.
- El cambio de geometría ahora se realiza con suspensión nativa de repintado de Windows (WM_SETREDRAW) y un único repintado final.
- El objetivo es evitar que Tk/CustomTkinter/Matplotlib expongan estados intermedios de tarjetas, separadores y gráficos durante el reflow.
- Sin cambios en telemetría, REAL_OR_NA, Gaming, Benchmark o diagnóstico.

## V305
- Base V304 Windows-only.
- Sidebar: transición atómica basada en un fotograma real de la ventana.
- Se elimina del flujo activo la máscara de borde, la estela y el reflow visible por etapas.
- Tk/CustomTkinter y Matplotlib terminan de acomodarse detrás del fotograma congelado y el estado final se publica de una sola vez.
- Sin cambios en telemetría, diagnóstico ni política REAL_OR_NA.

## V304
- Base V303.
- Contrato de plataforma consolidado: CorePulse queda exclusivamente orientado a Windows 10/11 x64.
- Eliminados backends, rutas de apertura, bindings y archivos alternativos de otros sistemas operativos.
- Runtime multi-Python se mantiene para CPython 3.12+ x64 dentro de Windows, con validación completa del stack.
- Sin cambios en REAL_OR_NA, REAL_FPS_OR_NA_ONLY, telemetría, benchmark ni diagnóstico.

## V303
- Base V302.
- Sidebar: se reemplaza la máscara/wipe de pantalla completa por una micro-transición localizada de borde.
- El dashboard permanece visible durante todo el abrir/cerrar del sidebar.
- Settle reducido y redraw único para disminuir parpadeos sin una cortina invasiva.

## V302
- Base V301.
- Sidebar: nueva transición de máscara/wipe para ocultar el reflow visual al abrir/cerrar el lateral.
- Durante el cambio de geometría se congela visualmente el contenido, se estabilizan los gráficos y luego se revela el dashboard con una cortina breve desde el borde izquierdo.
- No reconstruye el sidebar y no modifica telemetría, gráficos ni datos; sólo controla el ruido visual de renderizado.

## V301
- Base V300.
- Resumen: se aumenta la separación superior de la tarjeta de gráficos (CPU/RAM/GPU) para que quede visualmente más abajo respecto al bloque de almacenamiento.
- Ajuste puramente visual; no modifica telemetría ni lógica de gráficos.

## V300
- Base V299; conserva el fix universal de frecuencia CPU y el runtime multi-Python.
- Sidebar: Personalización deja de anclarse al borde inferior por entrar en modo compacto.
- El bloque Temas / Actualizaciones / versión permanece inmediatamente después de Historial en cualquier ancho o DPI.
- En alturas realmente bajas (<690 px) solo se compactan alturas/paddings; no se crea un hueco artificial.

## V299
- Base V298.
- Frecuencia CPU universal: mantiene LibreHardwareMonitor como fuente prioritaria y agrega fallbacks reales/trazables para equipos que no exponen sensores Clock.
- Fallback 1: `psutil.cpu_freq().current`.
- Fallback 2: `Win32_PerfFormattedData_Counters_ProcessorInformation` usando `ProcessorFrequency` y `PercentProcessorPerformance` reales del sistema.
- Fallback 3: `Win32_Processor.CurrentClockSpeed`.
- La capa certificada conserva fuente, sensor, timestamp y bandera `derived_from_real`; no inventa ni aplica offsets.
- Mantiene `REAL_OR_NA` y devuelve N/A si ninguna fuente real entrega frecuencia.

## V298
- Base V297.
- Corrige el arranque directo con un Python 3.12+ que no tenga `customtkinter` u otras dependencias instaladas.
- `main.py` y `corepulse_launcher.py` ahora aprovisionan automáticamente un venv aislado para el mismo minor de Python antes de importar la GUI.
- El bootstrap intenta primero el lock reproducible y luego una resolución adaptable; sólo registra el runtime si pasa la validación completa de Windows.
- Se elimina el fallo inmediato `ModuleNotFoundError: customtkinter` como ruta normal de primer arranque.

## V297
- Base V296.
- Runtime fuente multi-Python: CorePulse ya no exige exactamente Python 3.12; acepta CPython 3.12+ x64 sin límite menor artificial.
- `instalar_dependencias.bat` detecta automáticamente el Python disponible (incluido 3.13/3.14), crea un runtime aislado por versión y valida el stack completo antes de declararlo compatible.
- Se mantiene un lock reproducible como primer intento y se agrega una resolución flexible compatible para versiones nuevas de Python cuando un wheel exacto no exista.
- `main.py` y `corepulse_launcher.py` pueden redirigirse al runtime validado si se ejecutan desde otro Python sin dependencias.
- `build_exe.bat` deja de exigir Python 3.12 exacto y usa el runtime validado 3.12+ x64.
- La compatibilidad nunca se finge: si pythonnet / pywin32 / HardwareMonitor / LibreHardwareMonitor no cargan, la instalación falla y esa combinación de Python no se declara equivalente.

## V296
- Base V295.
- Gaming Inicio: corrección real del bloque de recursos para que CPU/GPU/RAM queden como una fila baja de tarjetas rectangulares, no columnas altas.
- Se reduce el ancho reservado a recursos y se da más aire al recuadro principal del juego actual.
- Ajuste fino del bloque derecho para mantenerlo horizontal y legible.

## V295
- Base V294.
- Gaming Inicio: corrección de altura de las tres tarjetas CPU/GPU/RAM para evitar que se extiendan demasiado hacia abajo.
- Se mantiene el recuadro del juego actual como bloque horizontal principal, con su composición intacta.
- Ajustes finos de padding y proporción para que el conjunto quede más balanceado.

## V294
- Base V293.
- Corregido el layout de CPU/GPU/RAM en Gaming: dejan de estirarse horizontalmente.
- Las tres tarjetas pasan a tamaño fijo rectangular y recuperan una distribución equilibrada con el bloque del juego actual.
- Se reemplaza el acento superior por un acento lateral más coherente con el lenguaje visual del Resumen.
- Sin cambios en telemetría real, Game Boost ni REAL_OR_NA / REAL_FPS_OR_NA_ONLY.

## V293
- Base V292.
- Gaming Inicio: corrección visual de las tres tarjetas de recursos (CPU/GPU/RAM).
- Las tarjetas quedan con proporción rectangular más clara, mejor jerarquía de texto y mejor alineación interna.
- Se mejora el ancho útil y la distribución del bloque de recursos sin tocar la lógica real de telemetría.

## V292
- Base V291.
- Corregido error al abrir Gaming: `transparency is not allowed for this attribute`.
- La flecha de retorno del header deja de usar un CTkButton con `border_color='transparent'`; ahora es un glifo CTkLabel clickeable sin cuadro de fondo.
- Se mantiene el icono Gaming sin cuadro, las tarjetas rectangulares CPU/GPU/RAM y el resto del diseño de V291.
- Sin cambios en telemetría real, benchmark ni contratos REAL_OR_NA / REAL_FPS_OR_NA_ONLY.

## V291
- Base V290.
- Cabecera Gaming: se eliminan los cuadros de fondo que sostenían la flecha de retorno y el icono de gaming; quedan solo los iconos.
- Inicio Gaming: se corrigen las tarjetas CPU/GPU/RAM, que ahora son rectangulares de forma consistente y con mejor ajuste visual.
- Juego actual: se ajusta el tamaño del título cuando no hay juego activo para evitar cortes y desbordes.
- Sin cambios en telemetría real, benchmark ni contratos REAL_OR_NA / REAL_FPS_OR_NA_ONLY.

## V290
- Base V289.
- Gaming Inicio: tarjeta GAME BOOST ampliada para mejorar lectura y presencia visual.
- Se corrigen los problemas visuales de las tarjetas CPU/GPU/RAM aumentando tamaño, área útil y ajuste de texto.
- El bloque del juego actual se amplía con carátula más grande y jerarquía visual más clara.
- Sin cambios en telemetría real, benchmark ni contratos REAL_OR_NA / REAL_FPS_OR_NA_ONLY.

## V289
- Base V288.
- Gaming Inicio: recursos CPU/GPU/RAM rediseñados como tarjetas cuadradas inspiradas en el lenguaje visual del Resumen.
- Bloque de juego actual ahora muestra carátula/artwork real del juego detectado junto a su nombre, manteniendo REAL_FPS_OR_NA_ONLY.
- Tarjeta de Perfil de rendimiento recortada verticalmente para mejorar el balance visual de la portada Gaming.
- Sin cambios en telemetría real, benchmark ni contratos REAL_OR_NA.

## V288
- Base V287.
- Game Boost absorbe la información útil de la antigua tarjeta de sesión.
- Nuevo layout: métricas CPU/GPU/RAM a la izquierda, Game Boost al centro y juego actual en una tarjeta principal.
- Se elimina el botón grande Configurar del extremo derecho; el acceso a ajustes queda como control discreto junto al título.
- FPS permanece REAL_FPS_OR_NA_ONLY y se muestra sólo dentro del bloque del juego cuando existe evidencia real.
- Sin cambios en la lógica del Game Boost, telemetría, perfiles o benchmark.

## V287
- Base V286.
- Eliminada únicamente la tarjeta superior de Sesión de juego en Gaming (juego detectado, FPS/CPU/GPU/RAM y accesos rápidos asociados).
- Se conserva intacto Perfil de rendimiento, Game Boost, cabecera Gaming, navegación y Benchmark.

## V286
- Base V285.
- Cabecera de Gaming aún más compacta.
- Eliminado el subtítulo gris bajo el título "Gaming".
- Reducida la altura del recuadro superior para una presencia más limpia y ajustada.
- Conserva flecha izquierda, icono de gaming a la derecha y el resto del layout aprobado.

## V285
- Base V284.
- Cabecera de Gaming recortada verticalmente para eliminar el espacio vacío inferior.
- Se añade icono de Gaming en la esquina superior derecha del recuadro, manteniendo la flecha profesional a la izquierda.
- Se conserva intacto el resto del layout aprobado: Inicio, Sesión de juego, Perfil de rendimiento y mejoras de Benchmark.

## V284
- Base V283.
- Corregida la distribución de la cabecera de Gaming según la revisión visual.
- Eliminada la tarjeta de estado superior derecha que sobrecargaba la cabecera.
- El bloque superior de Gaming ahora usa geometría cuadrada, flecha de retorno a la izquierda y título centrado.
- Se conservan sin cambios las tarjetas de Sesión de juego y Perfil de rendimiento aprobadas visualmente.
- Se mantienen las mejoras de Benchmark de V283 y no cambia la lógica REAL_OR_NA / REAL_FPS_OR_NA_ONLY.

## V283
- Base V282.
- Pulido de la cabecera de Gaming: botón de retorno minimalista con flecha y tarjeta superior de estado en formato cuadrado.
- Game Boost en Inicio queda más compacto, manteniendo la misma identidad visual.
- Benchmark recibe un rediseño visual más coherente con el lenguaje actual de CorePulse: cabecera profesional, tarjeta de estado, navegación y estado de carga más cuidados.
- Sin cambios en telemetría real, benchmark real ni contratos REAL_OR_NA / REAL_FPS_OR_NA_ONLY.

## V282
- Base V280; V281 descartada por interpretación visual demasiado literal del Resumen.
- Gaming conserva su propia estructura y adopta sólo el lenguaje visual del dashboard: superficies, bordes, radios, jerarquía tipográfica, acentos laterales y estados activos.
- Pulido de cabecera, navegación, sesión de juego, métricas, perfiles y Game Boost sin clonar la composición del Resumen.
- Sin cambios en telemetría real, diagnóstico, benchmark, SMART ni contratos REAL_OR_NA / REAL_FPS_OR_NA_ONLY.

## V280
- Base V279.
- Corregido el cierre/apertura del sidebar para reutilizar el árbol ya construido en lugar de destruirlo y reconstruirlo al reabrir.
- Eliminada la resincronización forzada de todo el dashboard en cada toggle; el cambio de visibilidad queda limitado a la geometría mínima necesaria.
- Se conserva la X por hover de V279 y las mejoras de navegación/Benchmark de V279.
- Sin cambios en telemetría, sensores, SMART, diagnóstico, benchmark real ni contratos REAL_OR_NA / REAL_FPS_OR_NA_ONLY.

## V279
- Base V277 (V278 descartada).
- Estabilizado el hover de la X del sidebar: la geometría del control queda fija y sólo cambia su contenido visible; se elimina el bind recursivo sobre todos los widgets hijos.
- Añadido debounce de salida del sidebar para evitar parpadeos al cruzar botones, iconos, labels y separadores.
- Navegación a Benchmark publicada en dos fases: pre-mapeo oculto detrás de la vista actual + commit en el siguiente frame.
- El contenido pesado del Benchmark se construye en un staging host fuera del viewport y se intercambia cuando ya está listo, conservando el estado de carga hasta entonces.
- Sin cambios en telemetría, sensores, benchmark real, SMART, diagnóstico ni contratos REAL_OR_NA / REAL_FPS_OR_NA_ONLY.

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
