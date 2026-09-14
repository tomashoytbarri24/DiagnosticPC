> **CorePulse V126** — Centro de salud de Windows con tarjetas de resumen grandes y acceso a Temas reforzado.


> Versión de desarrollo actual: **V126**

# CorePulse V122

**Versión actual: V122.** El número más alto es siempre la versión más reciente.



## V121 — Inicio de Windows seguro y reversible
- Startup Analyzer muestra fabricante, ubicación, estado e impacto con evidencia de Windows.
- Sólo permite deshabilitar entradas de usuario con rollback exacto; las entradas de sistema quedan en observación.

## V120 — Estado general explicable
- Centro de Salud resume el estado con evidencia real y muestra qué factores/fuentes justifican la conclusión.
- Sensores N/A no generan penalizaciones ni valores inventados.

## V119 — Recuperación tras cierres bruscos
- CorePulse detecta sesiones anteriores no cerradas limpiamente y registra recuperaciones temporales seguras.
- Los tweaks persistentes del usuario no se revierten automáticamente.

## V118 — Actualizaciones internas por GitHub Releases
- `Actualizaciones` permite a Maxi y Tomás comprobar releases sin descargar/clonar manualmente una copia sólo para probar una versión publicada.
- `Pruebas internas` acepta prereleases y `Estable` sólo releases finales.
- GitHub publica el digest SHA-256 del asset y CorePulse lo verifica antes de habilitar instalación o preparación.
- En desarrollo/fuente la versión descargada se extrae a `%LOCALAPPDATA%\CorePulse\updates\staged` y se abre como copia aislada; el repositorio actual no se sobrescribe.
- En una build instalada, CorePulse prioriza `CorePulse_Setup_V*.exe` y abre el instalador verificado.
- El sistema es manual en V118: no busca ni instala actualizaciones por sorpresa al iniciar.

## V117 — Antes vs Después por operación
- Incluye todo V116 y añade sesiones automáticas para Tweaks y Limpieza.
- Procesos, RAM, CPU, GPU, batería y almacenamiento se comparan sólo cuando hay lectura real; FPS/latencia quedan N/A si no existe una muestra válida.
- Las acciones que requieren reinicio no generan un resultado posterior ficticio.

## V116 — Historial longitudinal de salud
- Cronología diaria y comparación 7 vs 7 / 30 vs 30 días basada sólo en muestras reales.
- Los análisis de Estabilidad de Windows ya ejecutados se guardan como snapshots reutilizables.
- Migración automática de la base de historial existente, sin perder muestras anteriores.

## V115 — Reportes persistentes en AppData

- El PDF ya no pide una carpeta distinta en cada generación. Se guarda automáticamente en la carpeta de diagnóstico de CorePulse bajo AppData.
- Entrar a Diagnóstico no genera un PDF: el usuario decide cuándo crearlo con `Generar PDF`.
- `Abrir último PDF` recupera también el PDF más reciente de AppData tras reiniciar o actualizar CorePulse.
- `Abrir carpeta de informes` abre la ruta fija incluso si todavía no existe un PDF.
- El PDF no se abre por sorpresa al terminar; queda disponible mediante las acciones explícitas de Diagnóstico.
- Diagnóstico incorpora un acceso directo `Sensores y compatibilidad` hacia la trazabilidad completa de telemetría.


## V114 — Historial, sensores y acceso a reportes

- El benchmark conserva sesiones completas y permite revisar resultados anteriores del mismo PC.
- CorePulse compara el resultado actual con la última ejecución equivalente cuando coinciden perfil y componentes.
- La vista de benchmark incluye compatibilidad de sensores usando la matriz de capacidades del snapshot certificado, sin sondeos redundantes.
- Diagnóstico añade accesos persistentes para abrir el último PDF generado o abrir su carpeta.
- REAL_OR_NA se mantiene: una lectura no expuesta se muestra como N/A y no se estima.

## V113 — Benchmark configurado antes de ejecutar

- El benchmark ya no ofrece una acción directa antes de mostrar la configuración.
- Primero se elige perfil (Rápido/Estándar/Extendido) y luego CPU/RAM/SSD/GPU.
- El botón Ejecutar benchmark aparece al final del bloque de configuración y sólo se habilita si hay al menos un componente seleccionado.
- Desde Estabilidad, la acción ahora abre Configurar en vez de lanzar una prueba inmediatamente.

## V112 — Estabilidad más clara y artwork NVIDIA App universal

- La sección Estabilidad resume primero lo importante y deja el registro técnico plegado por defecto.
- Las recomendaciones se presentan como Qué pasó / Qué significa / Haz esto primero / Si se repite.
- La biblioteca Gaming aprovecha artwork local de NVIDIA App usando `%LOCALAPPDATA%` y `ApplicationStorage.json` del usuario actual, sin rutas ni juegos codificados para un PC concreto.
- Runtime, salud de discos y benchmark permanecen sin cambios.

## V110 — Centro de Salud precargado y optimizado

- La presencia de batería se decide antes del primer render del Centro de Salud.
- En laptops, Batería aparece desde el primer frame; en escritorios sin batería se omite desde el inicio.
- Battery Health detallado se recopila una sola vez en background y se comparte por cache.
- Hardware comparado se difiere hasta Historial y se reutiliza durante cinco minutos.
- No se modifica la lógica SMART/salud de discos ni el runtime universal.

## V107 — Benchmark configurable por perfiles

El benchmark de Gaming permite elegir **Rápido**, **Estándar** o **Extendido** y seleccionar individualmente CPU, RAM, SSD y GPU. Las pruebas omitidas no se tratan como fallos y cada perfil conserva carga real, telemetría durante la ejecución y protección térmica.



## V106 — Benchmark sostenido real

- Nueva suite estándar de aproximadamente 35–55 segundos.
- CPU: tramo single-thread + multinúcleo sostenido con SHA-256 nativo.
- RAM: copia sostenida de bloques grandes con tamaño adaptado a la memoria disponible.
- SSD: escritura + `fsync` + lectura secuencial de un archivo temporal de hasta 512 MB.
- GPU: carga OpenGL real sin WinSAT D3D ni necesidad de elevación; reporta el renderer que atendió la prueba.
- Progreso en vivo y muestreo térmico durante toda la carga, con corte de seguridad por temperatura extrema.
- Sin overclock, sin cambiar perfiles y sin rankings inventados.


## V104 — Gráficos responsivos del Resumen

- Gaming > Overlay permanece siempre visible; se elimina el botón Ocultar/Personalizar.
- El autoinicio de RivaTuner valida que el ejecutable sea exactamente `RTSS.exe`; nunca usa el ejecutable del desinstalador.
- El Startup Gate se centra en el monitor activo real, incluso si ese monitor tiene coordenadas negativas respecto de la pantalla principal.
- Runtime universal canónico preservado sin cambios.

## V100 — True Theme Replacement

- Los 10 temas reemplazan la paleta visual completa por roles exactos; no se aplica un filtro sobre el azul anterior.
- Vista previa y tema aplicado usan los mismos colores `bg`, `surface`, `surface_2`, `sidebar`, `border`, `text`, `muted`, `accent` y `accent_2`.
- Se eliminó el oscurecimiento acumulado causado por transformaciones repetidas de `theme_color()`.
- El runtime universal canónico permanece intacto y sigue viviendo por PC bajo `%USERPROFILE%\.corepulse\runtime\py312_<hash>`.

---

# CorePulse V0.10.2.92w — Battery Wear State Visual Refinement

## V0.10.2.92w — Battery Wear State Visual Refinement

- La tarjeta `Desgaste` gana altura y jerarquía dentro de Salud de batería.
- Ya no usa una barra visual: muestra directamente el porcentaje real disponible.
- El porcentaje cambia de color según el nivel de desgaste para lectura rápida, sin convertir el color en una causa o diagnóstico.
- `N/A` continúa mostrándose cuando no existe evidencia suficiente.
- El resto de las estadísticas de batería conserva la presentación introducida en la 90w.

## V0.10.2.89w — MemReduct-Style Deep RAM Reclaim
- `Liberar RAM > Profunda` usa un conjunto más amplio de mecanismos reales de Windows para reclamar memoria.
- Incluye trim de working sets, working sets del sistema, páginas modificadas, caché de archivos y listas standby cuando cada API está disponible.
- Requiere administrador para las operaciones profundas y tolera capacidades no soportadas sin simular resultados.
- CorePulse mide RAM antes/después y muestra únicamente lo realmente recuperado; no fija ni promete 99%.
- El modo Normal permanece conservador y Game Boost sigue purgando sólo standby.

## V0.10.2.88w — Windows Analysis Section Navigation
- Análisis de Windows deja de apilar Inicio, Servicios, Estabilidad y Controladores en una sola vista.
- Nueva navegación interna: Resumen / Inicio / Servicios / Estabilidad / Controladores.
- El resumen muestra sólo el estado de cada bloque y un acceso directo.
- Cada vista mantiene su análisis, paginación y evidencia existentes sin mezclar resultados.
- No cambia la lógica de detección, clasificación WHEA/BSOD, servicios ni controladores.

## V0.10.2.87w — Power Profile Shutdown Persistence Fix

- Corrige la regresión observada en Windows donde `CorePulse - Máximo rendimiento` podía cambiar a otro plan durante los segundos de cierre.
- CorePulse conserva el GUID exacto del último plan manual confirmado durante la sesión.
- Game Boost restaura primero sólo sus cambios temporales y, después, el gestor reafirma/verifica el plan persistente.
- `safe_shutdown` vuelve a verificar el GUID después de cerrar servicios temporales.
- `main.on_close()` ejecuta una última verificación de energía después de detener telemetría/sensores e inmediatamente antes de destruir la aplicación.
- Si el plan ya sigue activo, no se reescribe innecesariamente.
- Si el usuario cambia el plan desde Windows mientras CorePulse está abierto, ese cambio pasa a ser la nueva selección respetada.
- Al iniciar, la interfaz ya no inventa `Equilibrado` mientras el gestor aún no ha leído Windows; muestra estado pendiente hasta tener evidencia real.
- Game Boost sigue siendo temporal y el rollback de Tweaks permanece separado.

No se modifican telemetría, FPS, sensores ni las políticas `REAL_OR_NA` / `REAL_FPS_OR_NA_ONLY`.


## V0.10.2.85w — Gaming Sidebar Consolidation

- Se elimina `Gaming` como entrada visible del sidebar para evitar duplicidad de navegación.
- El acceso principal a Gaming queda centralizado en `Centro de salud > Rendimiento`.
- Al abrir Gaming u Overlay, el sidebar mantiene seleccionado `Centro de salud`, preservando la jerarquía del producto.
- La lógica Gaming, biblioteca, perfiles, Game Boost, estabilidad y Overlay permanece intacta.
- `btn_overlay` se conserva únicamente como referencia interna de compatibilidad y nunca se publica en el layout lateral.
- Sin cambios en telemetría, sensores, `REAL_OR_NA`, `REAL_FPS_OR_NA_ONLY` ni rollback.


## V0.10.2.84w — Gaming Session Hub UX Redesign

- Gaming pasa a una jerarquía centrada en la sesión: juego actual, métricas reales, perfil activo y acciones principales.
- Navegación principal estable: `Inicio / Biblioteca / Estabilidad / Overlay`.
- El inicio deja de exponer todas las herramientas a la vez; Game Boost y Overlay se abren sólo cuando el usuario los necesita.
- Los perfiles principales se simplifican a `Equilibrado / Rendimiento / Máximo`, manteniendo Ahorro de energía como opción secundaria.
- Estabilidad resume sesión, throttling, alertas y acceso a benchmark sin dejar una página vacía.
- Biblioteca usa grilla responsive real de 1/2/3 columnas y acciones contextuales sólo al hacer hover.
- Overlay muestra estado y vista previa primero; métricas, escala y posición quedan detrás de `Personalizar overlay`.
- FPS conserva `REAL_FPS_OR_NA_ONLY`; sin juego/fuente real se muestra `N/A`.
- Game Boost conserva su lógica reversible y rollback; esta versión reorganiza la UX, no amplía permisos ni automatiza cambios nuevos.

## V0.10.2.83w — Instant Detail Card Navigation

- Clic en CPU/RAM/GPU/almacenamiento responde primero y construye el detalle en el frame siguiente.
- Las fichas de hardware se conservan en caché para reaperturas prácticamente instantáneas.
- Los refrescos periódicos de CPU/RAM/GPU se pausan al ocultar la ficha.
- Se mantiene el hover contextual de `Ver detalles` de 82w y el Safe Storage Scanner de 81w.
- Sin cambios en fuentes de telemetría ni REAL_OR_NA.

CorePulse mantiene `REAL_OR_NA` y `REAL_FPS_OR_NA_ONLY`. Esta versión parte del diseño de limpieza previo al rediseño 79w/80w y añade únicamente un escáner conservador de almacenamiento.

## V0.10.2.82w — Hover Details Action Refinement

- En Resumen, `Ver detalles` queda oculto en reposo para CPU, RAM, GPU y almacenamiento.
- La acción aparece únicamente mientras el puntero está dentro de la tarjeta correspondiente.
- Mover el puntero entre labels, barras y el propio botón no provoca parpadeos.
- La tarjeta completa conserva su navegación por clic; no se modifica telemetría ni diagnóstico.

## V0.10.2.81w — Safe Storage Scanner

- `Liberar almacenamiento` ahora analiza las unidades locales fijas sin recorrer ni clasificar archivos personales.
- El usuario sólo ve archivos que el motor puede identificar mediante una allowlist determinista como temporales/cachés recreables y eliminables.
- Primera allowlist: temporales de usuario con antigüedad mínima de 24 h, temporales de Windows con antigüedad mínima de 24 h y caché de miniaturas de Explorer.
- No aparecen Descargas, Documentos, Escritorio, juegos, instaladores, crash dumps, DriverStore, WinSxS, Windows Installer ni rutas desconocidas.
- No se siguen symlinks, junctions ni reparse points; hardlinks se excluyen para no inflar el espacio recuperable.
- El escaneo comprueba que el archivo sea eliminable en ese momento y la limpieza revalida ruta, tamaño, fecha y regla antes de borrar.
- Los archivos nuevos o modificados después del análisis, bloqueados o que ya no cumplan la regla se omiten.
- La UI evita estados internos: muestra sólo el total eliminable, categorías encontradas y un botón `Liberar espacio` con una confirmación simple.
- El resultado posterior informa bytes/archivos realmente eliminados y, cuando puede medirse, el cambio real de espacio libre del volumen.
- RAM, caché y duplicados mantienen el diseño/flujo de la base 78w.

## V0.10.2.78w — Sidebar Navigation Hierarchy Polish

- Sidebar más estrecho y responsivo para devolver espacio al contenido principal.
- Identidad tipográfica compacta `CorePulse · Cereon Technologies`.
- Selección activa más sobria y jerarquía visual refinada.
- Tarjeta del agente simplificada y navegación más compacta.

## V0.10.2.77w — Evidence-Gated Stability Recommendations

- Se separan `hallazgo`, `interpretación`, `causa`, `confianza de causa`, `primer paso`, `escalamiento` y `evidencia`.
- La repetición de un fallo sólo aumenta la prioridad del hallazgo; no aumenta artificialmente la confianza en su causa.
- `Application Error 1000/1002` no implica automáticamente corrupción de instalación, RAM defectuosa, driver culpable ni DLL de Windows dañada.
- Reinstalar deja de ser una recomendación inicial automática: sólo aparece como escalamiento condicionado cuando el fallo persiste y sigue concentrado en la misma aplicación.
- `KERNELBASE.dll` y `ntdll.dll` se tratan como módulos asociados al cierre, no como prueba de que Windows esté dañado.
- Códigos como `0xc0000005`, `0xe0434352`, `0xc0000409` y `0xc0000374` aportan contexto, pero no se presentan como causa definitiva.
- WHEA, BSOD y Kernel-Power mantienen clasificación estricta y también separan hallazgo de causa.
- Sin hardcode de fabricante, modelo o software concreto.

## Startup foundation preserved

CorePulse mantiene sus contratos universales `REAL_OR_NA` y `REAL_FPS_OR_NA_ONLY`. La interfaz nunca convierte la ausencia de sensores, FPS, SMART, batería u otras capacidades en valores estimados.

### Startup / First Telemetry Ready Gate

- La pantalla de preparación sigue siendo la primera interfaz visible: `CorePulse está preparando tu equipo`.
- El Dashboard principal ya no se libera cuando el hilo de telemetría simplemente se inicia.
- `services` queda en 90% mientras CorePulse espera la primera muestra real del equipo.
- La telemetría debe ser adquirida por el worker, entregada al hilo de UI y renderizada correctamente antes de completar el gate.
- Antes de revelar el Dashboard, CorePulse ceba los gráficos con los historiales reales que ya llenó `telemetry_loop`; no crea muestras ficticias.
- `startup_metrics.json` registra `first_telemetry_acquired` y `first_telemetry_ui_ready` además de los hitos de layout, gráficos, servicios, integridad y revelado de ventana.
- Si un sensor concreto no existe o no es expuesto por el hardware/proveedor, sigue mostrándose `N/A`; la 64w sólo garantiza que CorePulse no muestre una interfaz todavía no alimentada por el monitoreo.
- Se conserva la arquitectura de startup de 61w/63w, el Centro de Salud pulido, Gaming comfort-first, Tweaks/rollback y EXE Runtime Integrity.
### Arranque automático en un PC nuevo — V0.10.2.94w
En Windows, la distribución fuente de CorePulse se inicia con `Iniciar_CorePulse.bat`. Si `.venv` no existe o está incompleto, CorePulse lo crea/repara automáticamente, instala `requirements-runtime-lock.txt`, valida el runtime y luego abre la aplicación con el Python local del proyecto. Ya no es necesario ejecutar manualmente `instalar_dependencias.bat` para un arranque normal.

La primera preparación necesita conexión a Internet porque los paquetes Python con binarios de Windows se obtienen desde pip/PyPI. Los siguientes arranques reutilizan el entorno local validado. Para builds reproducibles del EXE se mantiene `instalar_dependencias.bat` + `build_exe.bat`.
### Bootstrap resistente a fallos de pip — V0.10.2.96w

En un PC nuevo, CorePulse crea/repara `.venv` automáticamente. La actualización de `pip/setuptools/wheel` no es requisito para arrancar: se valida el `pip` local, se repara con `ensurepip` si hace falta y se instalan directamente las dependencias bloqueadas. Si la descarga real del runtime falla, el diálogo muestra el detalle de `pip` y mantiene `runtime_bootstrap.log` para diagnóstico.
