# V113 — Benchmark preconfigurable

- Flujo de benchmark reorganizado para configurar siempre antes de ejecutar.
- Se elimina el inicio directo desde la vista de Estabilidad; ahora abre la pantalla de configuración.
- Selector de perfil y componentes preceden al botón de ejecución.
- El botón queda deshabilitado cuando no hay componentes seleccionados y los controles se bloquean mientras la prueba está en curso.

# V112 — Estabilidad de Windows más clara + artwork universal de NVIDIA App

- Rediseño de la vista Estabilidad: resumen rápido de sistema/aplicaciones/reinicios y recomendaciones en lenguaje más directo.
- Se elimina del flujo principal el exceso de etiquetas técnicas de confianza/causa; la evidencia original queda separada como Registro técnico.
- La biblioteca Gaming puede reutilizar artwork local de NVIDIA App asociándolo mediante ApplicationStorage.json del usuario actual.
- La detección de artwork no contiene nombres de usuario, rutas de un PC concreto ni títulos de juegos codificados.
- Se preservan runtime universal, salud de discos, benchmark y lógica de diagnóstico.

# V111 — Estabilidad visual al redimensionar y navegar

- El Dashboard deja de reconfigurar todo el árbol de widgets en cada cambio de tamaño.
- Maximizar, restaurar y redimensionar usan un fast-path geométrico mientras no cambie el breakpoint responsive.
- Mover la ventana sin cambiar su tamaño no dispara ningún reflow.
- Las páginas nuevas se construyen fuera del viewport manteniendo visible la página actual hasta el commit final.
- Se elimina la transición visual de primera apertura que cubría el contenido.
- Las vistas cacheadas conservan posición, geometría y estado al cambiar de módulo.
- Los módulos GUI frecuentes se precargan por importación en background, sin crear widgets ni consultar hardware.
- El Overlay coalesce sus eventos de resize para evitar grid-forget repetitivo.

# V110 — Centro de Salud precargado y optimizado

- La presencia de batería se resuelve antes del primer render del Centro de Salud mediante API rápida y cache compartido.
- En laptops la tarjeta Batería aparece desde el primer frame; en escritorios sin batería no se crea.
- La recopilación detallada de batería permanece en background y powercfg sólo se usa como fallback.
- Se elimina el inventario comparado de hardware del camino crítico de la portada; se calcula al entrar a Historial y se cachea.
- El módulo del Centro de Salud se precarga en background después del arranque.
- No se modifica la lógica de salud SMART/almacenamiento.

# V109 — GPU Win64 + CPU benchmark temp + SMART NVMe %

- Corrige `argument 11: OverflowError` del benchmark OpenGL declarando ABI/argtypes Win32 pointer-safe en x64.
- El benchmark obtiene temperatura CPU directamente de sensores LHM reales cuando el alias certificado no está disponible durante la prueba.
- SMART NVMe prueba consulta por dispositivo y por adaptador/controlador para mejorar compatibilidad con NVMe detrás de VMD/RST.
- Cuando existe `Percentage Used`/`Wear` real, el Resumen muestra `Salud SMART XX%` calculada como vida restante a partir del desgaste reportado, sin transformar un simple estado `Healthy` en un porcentaje falso.

# V108 — GPU benchmark compatibility + benchmark telemetry + storage health

- Corrige el error de `ctypes.wintypes.HCURSOR` del benchmark GPU en builds de Python donde esos aliases Win32 no están exportados.
- El benchmark toma temperatura/frecuencia desde aliases y estructuras detalladas reales de telemetría, y usa las muestras de la propia prueba cuando el antes/después no está disponible.
- Añade lectura de salud de almacenamiento en segundo plano usando Windows Storage Reliability y NVMe SMART sin bloquear el arranque.
- Cuando sólo existe desgaste (`Wear` / `Percentage Used`), CorePulse muestra vida restante derivada y la etiqueta explícitamente como derivada.
- Mejora el fallback de capacidad física usando Win32_DiskDrive cuando LibreHardwareMonitor reporta 0/N/A.

# V107 — Benchmark configurable por perfiles

- Nuevos perfiles Rápido, Estándar y Extendido.
- Selección independiente de CPU, RAM, SSD y GPU.
- Ejecuciones parciales válidas: una prueba omitida no se marca como fallo.
- Progreso dinámico según los componentes seleccionados.
- Perfil Extendido orientado a observar rendimiento sostenido y comportamiento térmico durante más tiempo.
- Se conserva protección térmica y telemetría real durante la carga.

# V106 — Benchmark sostenido real

- Sustituye el benchmark de pocos segundos por una suite estándar de ~35–55 s.
- CPU sostenido con medición de 1 hilo y multinúcleo.
- RAM sostenida durante 8 s con buffer adaptativo.
- SSD secuencial real con archivo temporal, flush y fsync.
- GPU con workload OpenGL propio y renderer real, eliminando la dependencia de WinSAT D3D como supuesto benchmark gráfico.
- Progreso visual por etapas y telemetría térmica durante la prueba.
- Corte preventivo si CPU/GPU alcanzan temperaturas extremas.

# V105 — Tendencias ampliadas y aprovechamiento real del espacio

- Los gráficos CPU/RAM/GPU usan una porción mucho mayor del alto disponible.
- La tarjeta de tendencias escala con la altura real de la ventana.
- Almacenamiento deja de reservar espacio transparente sobrante con uno o dos discos.
- Mayor área útil del plot, títulos y ticks más legibles y líneas más visibles.
- Se conserva la escala porcentual real 0–100 y la telemetría sin inventar valores.

# V104 — Gráficos responsivos del Resumen

- Corrección de geometría de los gráficos del Dashboard para que no se deformen ni queden aplastados.
- Reflujo del FigureCanvas al redimensionar la ventana y al cambiar el espacio útil de la tarjeta.
- Altura mínima más legible para CPU, RAM y GPU en la zona de tendencias.
- La tarjeta de gráficos conserva presentación correcta en resoluciones y tamaños de ventana distintos.

# V103 — Acción directa de limpieza de RAM desde bandeja

- Se agrega **Limpiar RAM ahora** al menú del icono de CorePulse en la bandeja de Windows.
- La acción ejecuta directamente la limpieza segura de RAM; no abre ni redirige a Limpieza de sistema.
- La operación se realiza en segundo plano y muestra una notificación con el resultado real medido antes/después.
- Se evita lanzar dos limpiezas simultáneas desde la bandeja.
- Se preserva intacto el runtime universal canónico.

# V102 — Overlay fijo, RTSS seguro y Startup multi-monitor

- Gaming > Overlay permanece siempre visible; se elimina el control Ocultar/Personalizar.
- CorePulse sólo puede ejecutar un archivo cuyo nombre sea exactamente `RTSS.exe`; nunca usa `DisplayIcon` del registro de desinstalación, evitando abrir el uninstaller.
- El Startup Gate se centra en el monitor activo real de Windows y admite monitores con coordenadas negativas.
- El runtime fuente canónico permanece sin cambios.

# V101 — Overlay Minimal Professional Redesign

- Estado de RTSS convertido en una línea compacta en vez de una tarjeta grande.
- Métricas reducidas a filas compactas de lectura rápida, con menos altura y menos bordes.
- Vista previa convertida en un bloque pequeño y secundario.
- Diseño, escala, posición y atajo reunidos en una sola superficie de configuración.
- Se conservan atajo global exacto, autoinicio RTSS, políticas REAL_OR_NA y runtime universal canónico.

# V100 — True Theme Replacement

- Los 10 temas ahora reemplazan directamente los roles de color de la interfaz; ya no se mezclan con el azul original ni se oscurecen por remapeos sucesivos.
- `theme_color()` es idempotente: colores que ya pertenecen a la paleta activa no vuelven a transformarse.
- La vista previa y la interfaz aplicada usan exactamente `bg`, `surface`, `surface_2`, `sidebar`, `border`, `text`, `muted`, `accent` y `accent_2` de la misma paleta.
- Nueva convención simple de versión visible: V100, V101, V102... El número mayor es siempre el más reciente.
- Se preserva íntegramente el runtime canónico universal.

# V0.10.2.99w — Startup Integrity Deadlock Fix

- Corrige el bloqueo observado después de `Monitoreo en tiempo real activo`: el gate ya no depende indefinidamente de la auditoría profunda opcional.
- Layout, gráficos y primera telemetría real siguen siendo requisitos obligatorios antes de mostrar el panel.
- La auditoría profunda dispone de un watchdog de 12 s; si continúa, CorePulse abre el panel y la comprobación sigue en segundo plano.
- El sondeo de HardwareMonitor/pythonnet en modo fuente se ejecuta en un proceso aislado con timeout de 5 s para evitar bloqueos silenciosos de CLR.
- Se preserva sin cambios el runtime canónico bajo `%USERPROFILE%\.corepulse\runtime\py312_<hash>`.

# V0.10.2.98w — Exact Overlay Hotkey + Compact Metrics + RTSS Auto-Start

- **Base canónica preservada:** V0.10.2.97w `UNIVERSAL_RUNTIME_FIX`; no se reemplazan ni reescriben los resolutores de runtime/venv.
- Corrige el modificador **Alt fantasma** al grabar el atajo del Overlay: la captura ya no usa `event.state` y sólo conserva modificadores cuya tecla fue pulsada explícitamente.
- Los atajos heredados de la captura anterior se mantienen visibles pero no se registran hasta grabarlos una vez con la captura V2, evitando activar combinaciones contaminadas.
- `Métricas visibles` deja de estirarse hasta la altura del panel derecho; ambas columnas quedan alineadas arriba y la tarjeta recorta el espacio vacío sobrante.
- RTSS ahora intenta abrirse automáticamente al iniciar el Overlay, detecta si ya está ejecutándose, amplía la búsqueda de `RTSS.exe` y reintenta mientras la Shared Memory aún no está disponible.
- Se conservan Temas, startup visual aprobado, selección híbrida GPU y políticas `REAL_OR_NA` / `REAL_FPS_OR_NA_ONLY`.

# V0.10.2.97w — Theme Gallery Internal Module

- Reemplaza el botón Claro/Oscuro por **Temas**.
- Añade un módulo interno (sin Toplevel) con 10 temas predeterminados.
- Selector con scroll y respuesta inmediata.
- Vista previa en vivo sin alterar la interfaz actual.
- El botón **Aplicar tema** persiste la elección y reinicia sólo la UI para garantizar consistencia global.
- Compatibilidad automática con preferencias `dark` / `light` de versiones anteriores.
- Mantiene intacto el fix de runtime corto introducido en V0.10.2.96w.

# V0.10.2.96w — Short Runtime Path Fix

- El runtime fuente de Windows se instala en `%LOCALAPPDATA%\CorePulse\runtime\py312_<hash-lock>` en vez de `.venv` dentro del proyecto.
- Corrige `WinError 206`/rutas demasiado largas durante `pip install` en carpetas profundas.
- Bootstrap y relanzador comparten la misma ruta de entorno.
- El entorno de build también usa una ruta corta bajo `%LOCALAPPDATA%`.
- VS Code apunta al runtime de esta revisión para resolver `matplotlib`, `pythoncom` y dependencias instaladas.
- La distribución fuente ya no incluye un `.venv` roto o no portable.

# V0.10.2.95w — Bootstrap Pip Resilience Fix

- El primer arranque ya no depende de poder actualizar `pip`, `setuptools` y `wheel`.
- El `.venv` valida primero el `pip` incluido por Python 3.12 y usa `ensurepip` para repararlo sin Internet si fuese necesario.
- La primera operación de red útil instala directamente `requirements-runtime-lock.txt`.
- La instalación del runtime tiene reintento y conserva el detalle real de `pip` si falla.
- Un fallo opcional al refrescar herramientas de empaquetado ya no impide iniciar CorePulse.
- Se conserva el fix de relanzamiento `python.exe`/`pythonw.exe` de la 94w.

# V0.10.2.94w — Bootstrap Relaunch Loop Fix

- Corrige el bucle de reapertura del preparador en Windows.
- `source_runtime_bootstrap` reconoce como runtime local válido tanto `.venv\Scripts\python.exe` como `.venv\Scripts\pythonw.exe`.
- Tras preparar/reparar el entorno, CorePulse se relanza una sola vez con `pythonw.exe`.
- Mantiene la reparación automática del `.venv` y la validación de imports reales.


## V0.10.2.92w — Battery Wear Content Alignment Polish
- Mantiene intacta la tarjeta vertical de Desgaste.
- Ordena el contenido interno con el porcentaje centrado verticalmente.
- Añade una lectura breve `Bajo / Moderado / Alto` con el mismo color del desgaste.
- Sin barra de progreso y sin cambios en cálculo, fuentes o REAL_OR_NA.
# V0.10.2.92w — Battery Wear State Visual Refinement

## Centro de salud / Batería
- `Desgaste` deja de usar un remate tipo barra y pasa a una tarjeta vertical dedicada.
- La tarjeta ocupa la altura de las dos filas de detalles para dar más jerarquía al porcentaje de desgaste.
- El porcentaje usa color contextual: verde para desgaste bajo, ámbar para intermedio y rojo para alto; `N/A` permanece neutro.
- El color es sólo una ayuda visual y no se presenta como diagnóstico de avería.
- Capacidad, voltaje, corriente y carga/descarga conservan sus datos reales y trazabilidad.
- No cambia la recolección de batería, `REAL_OR_NA` ni el comportamiento desktop-aware.

# V0.10.2.89w — MemReduct-Style Deep RAM Reclaim

- `Profunda` amplía la liberación de RAM a working sets de procesos, working sets del sistema, lista de páginas modificadas, caché de archivos y listas standby.
- Usa `EmptyWorkingSet`, `NtSetSystemInformation(SystemMemoryListInformation, ...)` y `SetSystemFileCacheSize(-1, -1, 0)` cuando Windows y los privilegios lo permiten.
- Cada región se ejecuta como capacidad `best effort`; un fallo parcial no se reporta como éxito inventado.
- El resultado sigue siendo estrictamente medido antes/después y `target_percent` permanece `None`: no se promete 99% ni una cifra fija.
- Game Boost conserva su limpieza limitada exclusivamente a standby; no hereda el modo profundo.
- Sin cambios en telemetría, FPS, sensores, Safe Storage Scanner, perfiles de energía ni rollback.

# V0.10.2.88w — Windows Analysis Section Navigation

- Separación visual del módulo Análisis de Windows en cinco vistas internas.
- Resumen compacto con Inicio, Servicios, Estabilidad y Controladores.
- Una sola tabla/análisis visible por vez para reducir densidad y scroll.
- Se preservan paginación completa de Servicios y Estabilidad, clasificación por evidencia y análisis sólo lectura.
- Sin cambios en telemetría, sensores, Gaming, perfiles de energía, Safe Storage Scanner ni rollback.

# V0.10.2.87w — Power Profile Shutdown Persistence Fix

## Gaming / planes de energía
- Corrige la pérdida del plan persistente durante el teardown de CorePulse observada en Windows.
- La selección manual conserva el GUID exacto confirmado por `powercfg /getactivescheme`.
- Después de finalizar Game Boost, CorePulse verifica/reafirma el GUID persistente.
- `safe_shutdown` realiza una segunda verificación después de cerrar servicios.
- `main.on_close()` realiza la verificación definitiva después de telemetría/sensores y antes de `destroy()`.
- Reiniciar CorePulse lee el plan real que quedó activo; no fuerza `Equilibrado`.
- La UI usa `UNKNOWN` mientras el gestor aún no está disponible, evitando mostrar un plan falso durante startup.
- Se conserva rollback inmediato si la aplicación inicial del perfil falla.
- No cambia la temporalidad de Game Boost ni las políticas de telemetría real.

# V0.10.2.85w — Gaming Sidebar Consolidation

## Navegación / Gaming
- `Gaming` deja de publicarse como botón independiente en la barra lateral.
- `Centro de salud > Rendimiento` pasa a ser la única entrada visual principal al módulo Gaming.
- Los contextos internos `gaming` y `overlay` resaltan `Centro de salud` en el sidebar.
- Se elimina la ruta Gaming del dispatcher de botones laterales; `open_gaming()` y toda la funcionalidad del módulo permanecen disponibles desde Rendimiento.
- No se modifica telemetría, Game Boost, perfiles, biblioteca, Overlay ni políticas de datos reales.

# V0.10.2.84w — Gaming Session Hub UX Redesign

## Gaming / UX
- Inicio se convierte en un hub de sesión con juego detectado, FPS real/N/A, CPU, GPU, RAM y perfil activo.
- Navegación superior estable `Inicio / Biblioteca / Estabilidad / Overlay`; Benchmark permanece dentro de Estabilidad y Game Boost dentro de Inicio.
- Perfiles visibles reducidos a tres opciones principales; Ahorro de energía queda como acción secundaria.
- Game Boost separa estado de sesión y configuración; conserva snapshot/rollback existente.
- Estabilidad muestra estado de sesión, throttling, alertas, duración y benchmark en un mismo flujo.
- Biblioteca elimina tarjetas-resumen redundantes, usa grilla responsive 1/2/3 columnas y revela acciones sólo con hover.
- Overlay usa progressive disclosure: estado, vista previa y encendido siempre visibles; personalización avanzada oculta por defecto.
- Se preservan `REAL_OR_NA`, `REAL_FPS_OR_NA_ONLY` y las fuentes de telemetría existentes.

# V0.10.2.83w — Instant Detail Card Navigation

## Resumen / rendimiento de navegación
- CPU, RAM, GPU y almacenamiento publican un shell visible antes de construir el árbol CTk pesado.
- Se elimina `update_idletasks()` del camino de apertura de las fichas principales.
- Las cuatro fichas quedan cacheadas para reaperturas inmediatas.
- CPU/RAM/GPU pausan sus refrescos de 850 ms mientras están ocultas para no cargar el Dashboard en segundo plano.
- El panel real se adjunta al host ya publicado sin repetir `polish_widget_tree()` sobre todo el árbol.
- No cambia telemetría, sensores ni políticas REAL_OR_NA / REAL_FPS_OR_NA_ONLY.

# V0.10.2.82w — Hover Details Action Refinement

## Resumen / interacción
- `Ver detalles` ya no permanece visible en CPU, RAM, GPU ni almacenamiento.
- La acción se revela sólo mediante hover de la tarjeta y se oculta al abandonarla.
- Se usa comprobación del puntero sobre toda la jerarquía del card para evitar flicker entre widgets hijos.
- No cambia ninguna fuente de telemetría ni autoridad REAL_OR_NA.

# V0.10.2.81w — Safe Storage Scanner

## Limpieza / Almacenamiento
- Se restaura como base el diseño previo al rediseño de limpieza 79w/80w.
- `Liberar almacenamiento` gana flujo `Analizar` → `Liberar espacio`.
- Nuevo motor `core.safe_storage_cleanup` con política `ALLOWLIST_RECREATABLE_ONLY`.
- Sólo se publican candidatos de ubicaciones conocidas y recreables; cualquier ruta dudosa se ignora.
- Temporales recientes (<24 h), symlinks, junctions/reparse points, hardlinks, archivos bloqueados y rutas no locales quedan fuera.
- La limpieza usa exclusivamente la lista exacta del último análisis y vuelve a validar cada archivo antes de `unlink`.
- Se enumeran unidades locales fijas y se mide el espacio libre antes/después cuando está disponible.
- No hay borrado de documentos personales, Descargas, juegos, crash dumps, logs, Windows Update, DriverStore, WinSxS, Windows Installer ni carpetas desconocidas.

# V0.10.2.77w — Evidence-Gated Stability Recommendations

## Windows / Estabilidad
- Hallazgo confirmado y causa confirmada quedan separados.
- Frecuencia de eventos prioriza revisión, pero no inventa causalidad.
- Reinstalación sólo como escalamiento condicionado, nunca por un umbral de repeticiones.
- Evidencia de módulo y excepción incluye frecuencia real cuando está disponible.
- La UI explica `Qué sabemos`, `Interpretación`, `Causa`, `Primero prueba`, `Escalar sólo si` y `Evidencia`.
- `REAL_OR_NA` / `REAL_FPS_OR_NA_ONLY` preservados.

# V0.10.2.60w — Summary Trend Charts Cleanup

## Resumen
- Se elimina la fila inferior que repetía `Actual / Promedio / Pico` para CPU, RAM y GPU.
- La zona inferior queda dedicada exclusivamente a tendencias de telemetría.
- Se añade una sola cabecera `TENDENCIAS DE TELEMETRÍA`.
- Los gráficos CPU/RAM/GPU ganan altura útil y comparten exactamente la misma geometría.
- Se simplifican los títulos a `CPU (%)`, `RAM (%)` y `GPU (%)`.
- Se mantiene blitting y actualización rápida sin alterar los valores reales.

## Integridad
- `REAL_OR_NA` intacto.
- `REAL_FPS_OR_NA_ONLY` intacto.
- Sin cambios en sensores, diagnóstico, Gaming, Tweaks, rollback, PDF o EXE Runtime Integrity.

## V0.10.2.94w — Self-Bootstrapping Runtime Restore
- El modo fuente ya no depende de que un `.venv` preparado haya sido copiado desde otro PC.
- `Iniciar_CorePulse.bat` abre un bootstrap silencioso que crea o repara `.venv` automáticamente.
- Se añadió `requirements-runtime-lock.txt` separado de las dependencias de build.
- La preparación automática instala y valida Matplotlib, platformdirs y el stack runtime completo antes de publicar la GUI.
- `main.py` y `corepulse_launcher.py` redirigen al entorno local autoritativo si se ejecutan con otro Python en Windows.
- El entorno se valida mediante imports reales y presencia de LibreHardwareMonitor/HidSharp antes de marcarlo listo.
- Se conserva `instalar_dependencias.bat` como herramienta explícita de desarrollo/build, ya no como paso obligatorio para el usuario.
