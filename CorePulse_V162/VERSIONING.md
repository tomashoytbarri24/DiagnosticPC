## V161 — Diagnóstico con benchmark y telemetría

- Se elimina la ejecución automática de estrés y su cooldown; se conserva el motor interno.
- El benchmark existente mide CPU/RAM/SSD/GPU y observa sensores por componente con protección térmica y cancelación.
- Pantalla, evidencia, cobertura y PDF comparten el nuevo modelo.
- Validación y limitaciones: VALIDACION_V161.md.

## V159 — Redibujo por ventana y compatibilidad CTk

- El resize no aplaza dibujos de otras ventanas; se conserva el manejador original de tamaño/DPI.
- Liberación de pendientes y temporizador al salir; pruebas con conteo exacto de dibujos.
- 15 pruebas nuevas; ver VALIDACION_V159.md para resultados y límites.

## V158 — Redibujo CTk coalescido durante resize

- Se añade `gui/resize_render_guard.py`: mientras la ventana está en resize activo (`app.is_resizing`), los redibujos internos de CustomTkinter (`CTkBaseClass._draw`, disparado por cada widget en cada `<Configure>`) se coalescen y se aplican una sola vez por widget al soltar el borde, en vez de una vez por píxel arrastrado.
- Complementa —no reemplaza— el detector trailing de V148: ese debounce protege el trabajo propio de CorePulse (reflow de gráficos, modo de layout); esta guarda protege el costo interno de CustomTkinter, que antes quedaba fuera de cualquier debounce de la aplicación.
- Sin cambios de comportamiento fuera de un resize activo: cada redibujo real sigue aplicándose de inmediato.
- Preserva íntegro el ciclo de vida del Diagnóstico Completo de V157 (token por sesión, cancelación cooperativa, reinicio inmediato, evidencia, REAL_OR_NA); no se tocó `core/diagnostic_lifecycle.py`, `core/diagnostic_session.py`, `core/complete_diagnostic.py` ni `core/cancellable_process.py`.
- Publicación Git, drivers, benchmark y bandeja se revisaron y ya cumplían lo solicitado; no requirieron cambios.
- Detalle y limitaciones: VALIDACION_V158.md.

## V157 — Cancelación, aislamiento de sesiones y evidencia

- Diagnóstico reutilizable tras cancelar; callbacks y carga aislados por ejecución.
- Guardado/PDF sólo para resultados finalizados; protección térmica y métricas interrumpidas corregidas.
- Evidencia de RAM/GPU/almacenamiento y Windows parcial; REAL_OR_NA preservado.
- Detalle y limitaciones: VALIDACION_V157.md.

## V141 — Centro de salud compacto + optimización UI

- Resumen general compacto, legible y centrado en evidencia.
- Inventario técnico de CorePulse retirado de la portada.
- Menos widgets y autodiagnóstico lazy.

## V140 — Wear real de Windows + claridad de benchmark
- Windows Storage Reliability acepta `Wear=0` como 0% de desgaste sólo cuando el mismo contador expone actividad real (latencias de E/S, horas, ciclos o errores) y el disco figura Healthy/OK.
- Se incorporan FlushLatencyMax, ReadLatencyMax y WriteLatencyMax como evidencia de que el contador MSFT_StorageReliabilityCounter está vivo.
- La vista GPU deja de mostrar placeholders CPU/RAM N/A; sólo enseña las fases 3D realmente ejecutadas, incluida Carga combinada.
- El progreso deja claro que la ventana 3D termina antes que la barra global cuando después continúan CPU/RAM/SSD.
- Los resultados SSD muestran el volumen real donde se creó el archivo de prueba.
- `REAL_OR_NA`: ningún porcentaje se deduce de Healthy por sí solo.

## V139 — Salud de almacenamiento multi-fuente

- Conserva SMART/NVMe nativo y añade fallbacks reales.
- Windows Storage Reliability puede producir vida restante desde Wear, incluyendo Wear=0 sólo con corroboración de contador vivo.
- smartctl/smartmontools puede completar NVMe Percentage Used y temperatura cuando está disponible.
- REAL_OR_NA: no hay porcentajes por modelo ni estimaciones genéricas.

## V138 — Benchmark enfocado + historial dedicado
- La vista Ejecutar deja de duplicar el historial al final: el único historial completo vive en la pestaña `Historial`.
- Selección rápida `Todos / Ninguno` para CPU, RAM, SSD y GPU sin iniciar ninguna carga.
- Compatibilidad de sensores en Benchmark se limita a CPU/RAM/GPU/almacenamiento; batería deja de contaminar la cobertura de esta pantalla.
- Historial añade filtro por estado, limpieza de filtros y exportación CSV de las sesiones visibles con renderer y métricas reales.
- Se conserva comparación equivalente del mismo equipo y política REAL_OR_NA sin rankings externos.
- Runtime universal y SMART/NVMe permanecen sin cambios.

## V137 — Historial de benchmark 2.0
- Nueva vista `Historial` dentro del módulo Benchmark, separada de la configuración/ejecución pero usando la misma base persistente.
- Filtros por perfil y componente, resumen de sesiones, fecha, duración, renderer real y resultados por CPU/RAM/SSD/GPU.
- Comparación automática únicamente entre ejecuciones equivalentes del mismo equipo; los porcentajes salen de mediciones reales guardadas.
- `Ver detalle` permanece dentro de la misma ventana y no vuelve a sondear hardware.
- Las nuevas sesiones guardan el renderer OpenGL dentro de la identidad persistida para mejorar la equivalencia futura.
- Runtime universal y SMART/NVMe permanecen sin cambios.

## V136
Detección robusta del clon Git y feedback explícito al revisar publicación.

# Versión actual: V141

V126 continúa V125 sin reemplazos brutos: refuerza el acceso a Temas y convierte la portada de Análisis de Windows en tarjetas grandes con resumen real y acceso diferido al detalle. Próxima versión: V127.

## V126 — Windows Health cards + Temas visible
- Temas conserva el `accent`/`accent_2` exacto de la paleta aunque el sidebar refresque su estado.
- Inicio, Servicios, Estabilidad y Controladores se presentan como tarjetas grandes 2×2.
- Cada tarjeta muestra cantidad real analizada y el elemento más pesado/importante sólo cuando existe evidencia.
- `Ejecutar análisis` corre el diagnóstico desde la portada; `Ver más` se habilita con un resultado real y abre la vista detallada existente.
- Las vistas detalladas conservan paginación, tablas y acciones previas.
- Runtime canónico y SMART/NVMe no se modifican.

## V125 — Benchmark real/configurable + restauración visible + Temas destacado
- El benchmark vuelve a configurarse **antes** de ejecutar: perfil Rápido/Estándar/Extendido y selección independiente GPU/CPU/RAM/SSD.
- GPU usa la escena OpenGL visible con cargas significativamente mayores; CPU, RAM y SSD usan las cargas sostenidas de `benchmark_engine` (SHA-256, copia de memoria y E/S secuencial con flush/fsync).
- La carga GPU registra el renderer real y avisa si Windows ejecutó OpenGL en un adaptador distinto al que CorePulse está supervisando.
- La pestaña Benchmark se reorganiza como `1 Intensidad → 2 Qué medir → 3 Ejecutar`, con estimación de duración y botón principal destacado.
- Recuperación lista todos los puntos que `Get-ComputerRestorePoint` devuelve, mostrando descripción, fecha/hora, tipo y número de secuencia, más acción `Actualizar lista`.
- El botón `Temas` se vuelve una acción visual primaria dentro de `PERSONALIZACIÓN` y usa el accent exacto del tema activo.
- Runtime universal y lógica SMART/NVMe permanecen byte por byte sin cambios.

# Versionado de CorePulse

CorePulse usa numeración simple y creciente.

- V100 < V101 < ... < V121 < V122 < V123 ...
- El número mayor es siempre la versión más reciente.
- Versión actual: **V133**.

El sistema de runtime canónico NO depende del número de versión y se conserva desde la base universal corregida.




## V133 — Balance vertical de Personalización
- En ventanas restauradas con poco alto, Personalización adopta un modo vertical ajustado aunque el ancho siga clasificando la interfaz como estándar.
- `Temas` y `Actualizaciones` conservan botones completos; se ocultan antes el subtítulo y la versión para evitar que Actualizaciones quede pegado al borde inferior.
- El bloque reduce sólo márgenes verticales secundarios, sin miniaturizar la navegación ni cambiar el comportamiento contextual de Temas.
- Runtime universal y SMART/NVMe permanecen sin cambios.

## V132 — Corrección de arranque CustomTkinter
- Corrige el crash de V131 al crear los botones Temas y Actualizaciones: `CTkButton` no acepta `padx`/`pady` en su constructor.
- El espaciado interno visual se conserva mediante el texto/alineación y el padding externo permanece en `.pack()`.
- Se añade una validación AST para impedir que vuelva a introducirse `padx` o `pady` como keyword de `CTkButton`.
- No cambia el diseño responsive ni el comportamiento contextual de Temas introducido en V131.
- Runtime universal y SMART/NVMe permanecen sin cambios.


## V131 — Personalización compacta + responsive estable
- Temas vuelve al comportamiento contextual: fondo transparente mientras está inactivo y `accent_2` únicamente al abrir su módulo.
- Temas y Actualizaciones se agrupan en una tarjeta única de Personalización con jerarquía visual, versión y marca integradas.
- El sidebar mantiene una anchura y alturas mínimas legibles en ventanas compactas; deja de reducir agresivamente navegación y CTA.
- Centro de Actualizaciones usa grid con un único tramo elástico: el changelog se adapta y el pie de acciones siempre permanece visible al maximizar/restaurar.
- Runtime universal y SMART/NVMe permanecen sin cambios.

## V130 — Actualizaciones embebidas + CTA Temas estable
- Temas mantiene siempre `accent`/`accent_2` exactos, incluso durante reflows responsivos y antes del primer clic.
- Actualizaciones forma parte del sistema de navegación interna de CorePulse y ya no crea una segunda ventana.
- La página comprueba automáticamente el canal seleccionado y explica cuando no existe una Release publicada.
- SHA-256, backup, rollback y protección de checkouts Git de V129 se conservan.
- Runtime universal y SMART/NVMe permanecen sin cambios.

## V129 — Centro de Actualizaciones Seguro
- Canales Desarrollo y Estable sobre GitHub Releases.
- Descarga sólo el paquete publicado, sin clonar el repositorio.
- SHA-256 obligatorio mediante digest de GitHub o sidecar de checksums.
- Backup previo, helper de aplicación y rollback para copias fuente portables.
- Checkouts Git nunca se sobrescriben automáticamente.
- Runtime universal y SMART/NVMe permanecen sin cambios.

## V123 — Transporte SMART NVMe y fallback seguro
- La consulta `IOCTL_STORAGE_QUERY_PROPERTY` usa el buffer completo para entrada y salida, tal como recomienda Microsoft para datos NVMe protocol-specific.
- Mejora compatibilidad con miniports/controladores que rechazaban una cabecera de entrada de sólo 48 bytes aunque se solicitaran 512 bytes del Health Log.
- Si el SMART directo falla o lanza una excepción, CorePulse conserva `HealthStatus`/temperatura de Windows en vez de perder toda la ficha y mostrar N/A por un fallo secundario.
- Se mantiene `REAL_OR_NA`: no se inventa porcentaje si el Health Log no puede leerse.
- Sin reglas por Acer, MSI, Samsung ni modelos concretos.

## V122 — Autoridad SMART NVMe y validación de sentinels
- El SMART/Health Log NVMe directo tiene prioridad sobre valores consolidados de LHM/driver.
- `Percentage Used` NVMe se interpreta como desgaste: 0% usado => 100% restante; 6% usado => 94% restante.
- `Wear=0` de Windows Storage Reliability no se convierte automáticamente en 100% porque algunos controladores lo usan como valor no soportado.
- `0 °C` de almacenamiento se trata como N/A, no como temperatura física.
- La evaluación general deja de penalizar ceros ambiguos como si fueran salud SMART real.
- No hay reglas por fabricante/modelo; la política depende de autoridad y trazabilidad de la fuente.

## V121 — Startup Analyzer seguro y reversible
- Inicio de Windows muestra fabricante, ubicación, estado, RAM actual e impacto observado.
- Integra Registro Run/RunOnce, carpetas Startup, Win32_StartupCommand y Diagnostics-Performance 101.
- Sólo las entradas de usuario con rollback exacto pueden deshabilitarse desde CorePulse.
- Entradas de sistema, Microsoft, seguridad, HKLM u orígenes ambiguos quedan sólo en observación.
- Restauración reversible persistida en AppData; nunca se sobrescriben cambios externos.

## V120 — Evaluación general inteligente
- Centro de Salud incorpora una conclusión general explicable basada en evidencia real ya cargada.
- Combina telemetría, batería, almacenamiento, throttling, estabilidad de Windows y alertas activas cuando existen.
- No inventa porcentaje de salud ni penaliza sensores N/A.
- Expone factores y cobertura de fuentes para que el usuario entienda por qué aparece cada estado.

## V119 — Recuperación ante cierres no limpios
- Marcador persistente de sesión con heartbeat en AppData.
- Detecta si CorePulse anterior terminó sin ejecutar el cierre normal.
- Registra recuperación de cambios temporales que ya poseen rollback seguro (por ejemplo Game Boost).
- Tweaks persistentes elegidos por el usuario no se revierten automáticamente.
- El marcador se limpia únicamente después de completar el shutdown seguro.

## V118 — Actualizador interno por GitHub Releases
- Nuevo centro manual `Actualizaciones` accesible desde la barra lateral.
- Canal `Pruebas internas` incluye prereleases; `Estable` ignora prereleases.
- Consulta el repositorio `tomashoytbarri24/DiagnosticPC` mediante GitHub Releases.
- Descarga sólo bajo acción explícita y exige digest SHA-256 publicado por GitHub antes de preparar/abrir una actualización.
- En modo fuente nunca sobrescribe el repositorio: extrae una copia verificada en AppData para probarla en paralelo.
- En modo PyInstaller/instalado prioriza el instalador de la release y lo abre sólo después de verificarlo.
- Los scripts de build leen `core/version.py` para evitar nombres de instalador anclados a versiones antiguas.
- No hay actualización automática al inicio.


## V134 — Autodiagnóstico de capacidades de CorePulse
- Estado de CorePulse accesible desde Centro de Salud.
- Preflight real + matriz de sensores del snapshot actual; sin consultas sintéticas ni rankings.
- N/A representa capacidad opcional no instalada/presente/expuesta y no se interpreta como avería.
- Informe JSON técnico persistente para soporte y trazabilidad.
- Runtime universal y SMART/NVMe permanecen sin cambios.


## V135 — Publicación Git segura desde CorePulse
- Publicación a una rama de desarrollo desde el Centro de Actualizaciones.
- Mensaje de commit editable y push usando la autenticación Git existente.
- `FASE 1`, `FASE 2` y `FASE 3` quedan explícitamente fuera del staging y se validan antes/después.
- `main/master/trunk` y detached HEAD quedan bloqueados.
- Tras publicar se genera ZIP + SHA-256 preparado para GitHub Releases.


## V142
Diagnóstico Completo 2.0: escritorio + Windows + estrés + benchmark + correlación, con PDF opcional y sin reparaciones automáticas.


## V143
Informe vivo accionable del diagnóstico completo: estado por componente, evidencia resumida y navegación directa a CPU/GPU/RAM/almacenamiento/batería/Windows.


## V144
Navegación profunda atómica desde Diagnóstico: Centro de salud prepara pestaña y subsección antes de hacerse visible, eliminando flashes Resumen → Windows → destino.


## V145
- El botón X de Windows oculta CorePulse en la bandeja; el monitoreo continúa activo.
- El cierre real permanece en `Salir de CorePulse` y en reinicios/actualizaciones explícitos.
- Restaurar desde bandeja conserva estado maximizado o geometría normal.
- Modo ventana 1080p más holgado: preset recomendado migrado a 1560×860 y Dashboard compacto con menor consumo vertical.
- El layout maximizado/large no cambia.



## V146
- Diagnóstico Completo 2.1: pantalla final orientada a componentes y siguiente paso.
- CPU/GPU/RAM separan Estado, Estrés y Rendimiento medido; el benchmark no se usa como salud.
- Almacenamiento separa salud física de rendimiento; una unidad detectada no implica salud conocida.
- Windows resume Estabilidad, Drivers e Inicio con evidencia real.
- Prioridad única accionable cuando existe WARNING/CRITICAL; ninguna reparación es automática.
- El PDF usa la misma interpretación estructurada de la pantalla final.


## V147
- Resultado del Diagnóstico Completo adaptable a alturas y anchos distintos.
- Panel derecho con `StableScrollHost`: rueda/touchpad rápida, Canvas nativo y scrollbar estable.
- Tarjetas por componente más compactas sin eliminar Estado/Estrés/Rendimiento ni acciones.
- Breakpoints wide/medium/compact reducen el bloque visual izquierdo y evitan comprimir el informe.
- En anchos muy reducidos las tarjetas pasan automáticamente de 2 a 1 columna.
- Evidencia visible se resume a dos piezas; el detalle completo permanece en el módulo de destino/PDF.


## V148 — FLUID_WINDOW_RESIZE_AND_DIAGNOSTIC_BREAKPOINT_OPTIMIZATION
- Resize de ventana desacoplado del reflow pesado por píxel.
- Diagnóstico recompone sólo al cruzar breakpoints o al terminar el gesto.
- Gauge con redraw diferido.
- StableScrollHost difiere geometría pesada mientras Windows está redimensionando.
- Informe final usa 3/2/1 columnas según ancho disponible.


## V149 — COMPLETE_DIAGNOSTIC_TRACEABLE_EVIDENCE
- Cada tarjeta del Diagnóstico Completo incorpora `Ver evidencia` sin abandonar el informe.
- Evidencia separada por Escritorio, Estrés, Benchmark, salud física y Windows según corresponda.
- Se mantienen N/A y REAL_OR_NA cuando una métrica no fue expuesta.
- `Ir a ...` conserva la navegación al módulo especializado; evidencia y acción ya no se mezclan.
- El PDF reutiliza la misma evidencia estructurada de la pantalla final.
- El Diagnóstico Completo pasa a esquema interno 2.2-v149 sin cambiar la política de reparación explícita.


## V150 — COMPLETE_DIAGNOSTIC_FINAL_ORCHESTRATION
- Diagnóstico Completo 3.0 finalizado como flujo principal: escritorio, hardware, Windows, estrés, enfriamiento, benchmark y correlación.
- Cancelación cooperativa segura durante observación, estrés y benchmark; una ejecución cancelada no se publica como diagnóstico final.
- Cobertura explícita de fases en vez de presentar la confianza de la fase pasiva como confianza global.
- Comparación informativa con el diagnóstico completo anterior por CPU/GPU/RAM/almacenamiento/batería/Windows.
- El historial nunca se usa como fuente de fallos actuales.
- Pantalla y PDF comparten componentes, evidencia, prioridad, cobertura y comparación.
- REAL_OR_NA, benchmark sin ranking externo y reparaciones sólo bajo acción explícita.

## V151 — Diagnostic Cancel + Git Publish Hotfix
- Reinicio inmediato del diagnóstico después de cancelar.
- Publicación segura cuando la versión remota anterior ya fue eliminada localmente.
- Layout compacto de Actualizaciones/Publicar y explicación explícita de la versión registrada en Git.


## V152 — Safe Existing Target Publish Hotfix
- Publicar acepta una carpeta `CorePulse_V152` ya existente sólo cuando coincide byte a byte con la versión actual (ignorando cachés/logs).
- Si el destino difiere, la publicación se bloquea para proteger cambios locales.
- El registro de Publicar ocupa ahora el espacio flexible y elimina la fila vacía que deformaba la vista.
- Mantiene FASE 1/2/3 fuera del commit.

## V153 — SAFE_UNTRACKED_TARGET_SYNC_PUBLISH_HOTFIX
- Corrige el bloqueo de Publicar cuando la carpeta destino de la versión nueva ya existe localmente pero aún no está registrada en Git.
- Si la carpeta destino difiere y no está rastreada/staged, CorePulse la respalda fuera del repositorio, sincroniza la versión en ejecución y continúa la publicación.
- Si existen cambios Git reales en la carpeta destino, la publicación sigue bloqueándose para evitar pérdida de trabajo.
- Mantiene protegidas FASE 1, FASE 2 y FASE 3.

## V154 — REPOSITORY_BRANCH_PUBLICATION_ARCHITECTURE
- Separa explícitamente repositorio local, remoto `origin`, rama destino y carpeta CorePulse a publicar.
- `CorePulse_V154` deja de etiquetarse como “destino”; es sólo la carpeta versionada dentro del checkout.
- Publicación compatible con cualquier ruta/nombre local del clon en PCs distintos.
- Muestra URL navegable de la rama GitHub cuando el remoto permite derivarla.
- Publicar rama deja de generar automáticamente paquetes ZIP/SHA de GitHub Release.
- Corrige doble `shutil.move` en respaldo de destinos locales no rastreados.

## V155 — ROBUST_BRANCH_PUBLISH_WITH_LOCAL_PRESERVATION
- El destino Git vuelve a ser inequívocamente `origin/<rama activa>` del clon seleccionado; la URL navegable de la rama se muestra antes de publicar.
- Las versiones CorePulse anteriores se retiran sólo del índice Git (`git rm --cached`): si existen localmente, permanecen en disco incluso cuando tienen cambios.
- Una carpeta `CorePulse_V155` preexistente y distinta se respalda fuera del repositorio antes de sincronizar la versión en ejecución.
- Sólo bloquean estados que sí podrían mezclar trabajo ajeno al commit: rama principal/detached HEAD, ausencia de FASE 1/2/3, remoto origin ausente o archivos staged fuera de CorePulse.
- El botón de publicación muestra explícitamente la rama real, por ejemplo `Publicar en maxi/corepulse-v128`.
- FASE 1, FASE 2 y FASE 3 continúan fuera del commit y se verifican antes/después.

## V156 — GENERAL_UI_READABILITY_AND_DRIVER_SEMANTICS_POLISH
Pulido de legibilidad, semántica precisa de controladores, diferenciación de Alertas técnicas y reducción de microcopy redundante. Publicador y resize quedan fuera de alcance.
## V160 — COMPLETE_DIAGNOSTIC_INTEGRATED_VERDICT
- El resultado final explicita Estado en escritorio, Estrés y Benchmark como dimensiones separadas en CPU/GPU/RAM.
- Se añade un resumen integral por áreas y cobertura de fases, sin crear scores nuevos.
- Almacenamiento separa salud física, espacio utilizado y benchmark.
- Pantalla y PDF reutilizan el mismo resumen determinista REAL_OR_NA.
- Sin cambios en runtime protegido, SMART/NVMe, publicación Git ni optimización de resize.


## V161 — DIAGNOSTIC_BENCHMARK_LOAD_TELEMETRY
- Diagnóstico Completo elimina el stress automático y usa benchmark CPU/RAM/SSD/GPU como única fuente de carga normal.
- La telemetría se recoge durante el benchmark y se conserva separada del rendimiento medido.
- Cancelación/reinicio, seguridad térmica, PDF e historial permanecen bajo REAL_OR_NA.
- El publicador Git reconoce la carpeta real ejecutada y preserva FASE 1/2/3 y cambios ajenos.

## V162 — BENCHMARK_2_0_METHOD_CONSISTENCY
- Benchmark y Diagnóstico reutilizan la misma metodología GPU visual multifase; la carga OpenGL simple queda sólo como motor interno/compatibilidad.
- La identidad GPU normaliza únicamente sufijos técnicos conocidos del renderer y exige coincidencia única antes de atribuir sensores.
- SSD intenta I/O directo de Windows (`NO_BUFFERING` + `WRITE_THROUGH`) para reducir influencia de caché; cualquier fallback queda marcado como potencialmente cacheable.
- RAM se presenta como tasa de copia sostenida del proceso CorePulse, no como ancho de banda DDR teórico.
- Benchmark mide; Diagnóstico interpreta. Se eliminan conclusiones térmicas genéricas del resumen de benchmark.
- La metodología queda versionada (`COREPULSE_BENCHMARK_2`) y el historial sólo calcula variaciones entre sesiones equivalentes; SSD exige mismo volumen/modo de E/S.
- Se conserva el Diagnóstico sin stress automático y el publicador Git corregido de V161.
