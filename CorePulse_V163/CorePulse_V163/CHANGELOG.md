## V159 — Redibujo por ventana y compatibilidad CTk

- El resize no aplaza dibujos de otras ventanas; se conserva el manejador original de tamaño/DPI.
- Liberación de pendientes y temporizador al salir; pruebas con conteo exacto de dibujos.
- 15 pruebas nuevas; ver VALIDACION_V159.md para resultados y límites.

## V157 — Cancelación, aislamiento de sesiones y evidencia

- Diagnóstico reutilizable tras cancelar; callbacks y carga aislados por ejecución.
- Guardado/PDF sólo para resultados finalizados; protección térmica y métricas interrumpidas corregidas.
- Evidencia de RAM/GPU/almacenamiento y Windows parcial; REAL_OR_NA preservado.
- Detalle y limitaciones: VALIDACION_V157.md.

## V146
- Diagnóstico Completo 2.1 con informe final por componente.
- CPU/GPU/RAM separan Estado, Estrés y Rendimiento medido.
- Almacenamiento separa salud física de benchmark y conserva N/A cuando falta evidencia real.
- Windows resume Estabilidad, Drivers e Inicio.
- Una franja de Prioridad indica el siguiente paso cuando existe WARNING/CRITICAL.
- PDF y pantalla reutilizan la misma interpretación; sin reparaciones automáticas ni rankings externos.


## V141
- Centro de salud más compacto: resumen general con tipografía mayor y evidencia útil sin espacio vacío.
- `Seguimiento recomendado` reemplaza el rótulo ambiguo `Conviene vigilar`.
- La tarjeta pública de inventario `CorePulse` sale de la portada; el autodiagnóstico técnico se conserva internamente.
- Tarjetas de módulos simplificadas con menos widgets decorativos y menor altura.
- Import lazy del autodiagnóstico para reducir trabajo al abrir Centro de salud.


## V139
- Salud de almacenamiento multi-fuente con prioridad a evidencia cuantitativa real.
- `Wear=0` de Windows sólo se acepta como 100% de vida si el contador de confiabilidad está corroborado por horas/ciclos/errores reales.
- Fallback opcional a `smartctl`/smartmontools para NVMe detrás de controladores que no reenvían el Health Log nativo.
- El detalle de almacenamiento identifica la fuente real usada para el porcentaje de vida restante.
- SMART/NVMe nativo existente se conserva sin modificaciones.
# CorePulse V136

- Publicación: selección de repositorio más robusta; acepta cualquier subcarpeta de un checkout Git.
- Si se selecciona una copia ZIP sin `.git`, CorePulse busca clones Git cercanos no recursivamente y adopta automáticamente un candidato inequívoco.
- `Revisar` ahora muestra hora de la comprobación, raíz Git, rama, remoto, FASE 1/2/3 y el motivo exacto del bloqueo.
- Mensaje específico para distinguir una carpeta extraída desde ZIP de un clon creado con `git clone`.
- Mantiene bloqueo de `main/master/trunk` y staging exclusivo de carpetas CorePulse versionadas.

# V134 — Autodiagnóstico de capacidades de CorePulse

- Centro de Salud incorpora una tarjeta `CorePulse` con acceso a un autodiagnóstico interno.
- El diagnóstico separa dependencias obligatorias, herramientas opcionales y sensores realmente expuestos por el equipo actual.
- Estados descriptivos: Disponible, Parcial, N/A, Info o Error; una capacidad opcional N/A nunca se convierte en fallo ni reduce una salud sintética.
- Reutiliza el último snapshot certificado para CPU/RAM/GPU/almacenamiento/batería y ejecuta el preflight de runtime en background para no bloquear la interfaz.
- Detecta de forma explícita PresentMon, RTSS, Ookla, WMI/pywin32/pythonnet, LibreHardwareMonitor, PowerShell, permisos y dependencias del runtime.
- Guarda un informe técnico local `corepulse_capabilities.json` en la carpeta de diagnósticos.
- Runtime universal y SMART/NVMe permanecen sin cambios.

# V133 — Balance vertical de Personalización en modo ventana

- Ajusta únicamente el bloque lateral de Personalización cuando el alto útil es limitado.
- `Temas` y `Actualizaciones` mantienen tamaño legible y el mismo comportamiento contextual.
- Se eliminan primero metadatos secundarios (`Apariencia y versión`, divisor y versión) para que `Actualizaciones` no quede forzado contra el borde inferior.
- No cambia el layout principal, telemetría, runtime canónico ni SMART/NVMe.

# V132 — Hotfix de arranque CustomTkinter

- Eliminados `padx` no soportados de los constructores `CTkButton` de Personalización.
- Conservado el padding externo y el comportamiento visual de V131.
- Añadida prueba preventiva para kwargs no soportados en `CTkButton`.

# V131 — Personalización refinada + layout responsive estable

- `Temas` vuelve a ser transparente cuando no está seleccionado y usa el color activo sólo mientras su módulo está abierto.
- `Temas` y `Actualizaciones` comparten una tarjeta de Personalización más limpia, con subtítulo y versión integrados.
- Sidebar compacto conserva ancho/altura/font mínimos legibles en vez de reducir demasiado sus elementos.
- `Centro de actualizaciones` cambia a un grid vertical estable: el panel de estado absorbe el espacio variable y las acciones inferiores ya no quedan cortadas al restaurar la ventana.
- El módulo reacciona al viewport sin destruir/recrear widgets.
- Runtime canónico y SMART/NVMe sin cambios.

# V130 — Actualizaciones integradas + Temas estable desde el arranque

- `Temas` conserva siempre su fondo accent exacto desde el primer frame; el reflow responsivo ya no puede volverlo transparente.
- `Actualizaciones` deja de abrir un `CTkToplevel`: ahora es una página interna cacheable dentro de la misma ventana principal.
- Búsqueda automática al entrar al módulo y al cambiar de canal, manteniendo `Buscar actualizaciones` como refresco manual.
- Flujo visible `Buscar → verificar SHA-256 → instalar/probar → rollback`, con mensajes claros cuando un canal aún no tiene Releases.
- Se conserva la protección de checkouts Git: nunca se sobrescribe la rama de desarrollo.
- Runtime canónico y SMART/NVMe sin cambios.

# V129 — Centro de Actualizaciones Seguro

- Centro rediseñado con canales Desarrollo/Estable, versión actual/nueva, fecha, tamaño y changelog.
- Descarga sólo el asset de release y exige SHA-256 verificable antes de permitir instalación.
- Acepta digest publicado por GitHub o checksum sidecar.
- Copias fuente portables: backup, aplicación diferida, relanzado y rollback.
- Checkouts Git: no sobrescribe la rama; mantiene preparación aislada para pruebas.
- UI alineada con roles exactos del tema activo.
- Runtime canónico y SMART/NVMe sin cambios.

# V126 — Windows Health Summary Cards + Theme CTA

## Centro de salud · Windows
- Portada 2×2 con tarjetas grandes para Inicio, Servicios, Estabilidad y Controladores.
- Cada tarjeta muestra cantidad analizada y el elemento más pesado/importante usando sólo datos reales disponibles.
- El análisis se puede ejecutar/actualizar desde la tarjeta.
- `Ver más` queda habilitado después de obtener un resultado y abre la vista detallada existente.
- Las tablas, paginación y acciones anteriores se conservan.

## Temas
- El botón Temas permanece destacado incluso después de los refrescos del estado de navegación.
- Usa `accent`, `accent_2` y roles de texto exactos de la paleta activa, sin filtros ni oscurecimiento.

## Integridad
- `REAL_OR_NA` preservado.
- Sin cambios en runtime canónico ni SMART/NVMe.

# V125 — Benchmark real configurable, puntos de restauración y Temas visible

- Benchmark configurable antes de ejecutar (Rápido / Estándar / Extendido; GPU / CPU / RAM / SSD).
- GPU 3D incrementa carga de geometría, fill, texturas, shaders y compute; CPU/RAM/SSD usan workloads sostenidos reales.
- Resultado informa renderer GPU real y detecta cuando Windows eligió otro adaptador.
- UI del benchmark reorganizada y botón `INICIAR BENCHMARK` destacado.
- Recuperación muestra la lista completa de puntos de restauración con fecha, descripción, tipo y secuencia.
- Nuevo `Actualizar lista` de puntos de restauración.
- `Temas` pasa a una sección visible de Personalización con color accent del tema activo.
- Sin cambios en runtime universal ni SMART/NVMe.

# V124 — Integración Tomás + Maxi, temas exactos y arranque tematizado

- Se conserva íntegramente la línea de trabajo de Tomás en V113: benchmark visual 3D multiphase, página principal Benchmark, mejoras de drivers, dashboard, sidebar, gaming/artwork y demás pruebas asociadas.
- Se integran sobre esa base las mejoras V114–V123 desarrolladas en paralelo: historial longitudinal, Antes vs Después automático, actualizador interno, recuperación de sesión, salud inteligente, Startup Analyzer, acceso PDF, diagnóstico de sensores y correcciones SMART/NVMe.
- La aplicación de temas deja de clasificar tonos estructurales por umbrales de luminosidad y usa el rol CorePulse original más cercano; el color aplicado es siempre el hexadecimal exacto de la paleta elegida.
- La pantalla de carga usa directamente `bg`, `surface`, `border`, `text`, `muted`, `accent` y `surface_2` del tema activo, por lo que también cambia al seleccionar un tema.
- El historial de benchmark se adapta al benchmark visual multiphase de Tomás sin reemplazarlo ni reintroducir el benchmark legacy como experiencia principal.

# V113 — Benchmark GPU principal por áreas

- Benchmark pasa a ser una página principal independiente de CorePulse, fuera de Gaming y Diagnóstico.
- La prueba visual OpenGL es ahora el benchmark principal visible.
- Ejecución dividida en cuatro cargas reales: Geometría, Fill / fragmentos, Texturas / VRAM y Carga combinada.
- Cada fase conserva sus propios FPS, 1% Low, frametime P95/P99 y resumen de telemetría real.
- La fase Texturas / VRAM crea recursos OpenGL reales y registra la memoria solicitada por la prueba sin presentarla como capacidad total de VRAM.
- El resultado principal corresponde a Carga combinada; no se fabrican rankings ni puntuaciones calibradas.
- Shaders programables, Compute y Ray Tracing no se etiquetan como medidos hasta existir una carga real específica para ellos.
- Se preservan warm-up, VSync auditado, resolución de cliente fija, protección térmica y REAL_FPS_OR_NA_ONLY.

## V123
- Corrección del transporte Win32 para SMART/Health Log NVMe: `DeviceIoControl` recibe el buffer completo como entrada/salida.
- Fallback robusto: un fallo de SMART directo ya no invalida el estado `Healthy/OK` obtenido desde Windows Storage.
- Evita volver a mostrar falsos `0%`; si no existe porcentaje fiable, se conserva estado cualitativo y N/A cuantitativo.
- Runtime canónico sin cambios.
# V118 — Internal Release Updater

## Actualizaciones / pruebas de distribución
- Centro manual `Actualizaciones` conectado a GitHub Releases de `tomashoytbarri24/DiagnosticPC`.
- Canal interno incluye prereleases; canal estable sólo releases finales.
- Descarga asíncrona con progreso y verificación SHA-256 mediante `asset.digest` de GitHub.
- Modo fuente: staging seguro en AppData y apertura de copia aislada, sin modificar el repositorio de desarrollo.
- Modo instalado: selección preferente del instalador y apertura sólo después de validación de integridad.
- Token opcional sólo por `COREPULSE_GITHUB_TOKEN`; no se persisten credenciales.
- Build EXE/installer usa la versión actual de `core/version.py`, eliminando nombres anclados a 96w.
- Runtime universal, SMART/NVMe y salud de discos sin cambios.

# V115 — AppData Report Workflow

- Los PDF de Diagnóstico vuelven a una ruta persistente bajo AppData usando `core.runtime_paths.diagnostics_dir()`.
- `Generar PDF` no abre un selector de carpeta y no se ejecuta automáticamente al entrar en Diagnóstico.
- El último informe se recupera por puntero persistente o, como fallback, escaneando el PDF más reciente en la carpeta de Diagnóstico.
- La carpeta de informes puede abrirse aunque aún no exista un PDF.
- La generación ya no abre automáticamente el visor; `Abrir último PDF` queda como acción explícita.
- Compatibilidad de sensores de V114 se conserva sin sondeos adicionales y continúa disponible dentro de Benchmark; Diagnóstico añade además un acceso directo a la trazabilidad completa de sensores.

# V114 — Historial de benchmark, diagnóstico de sensores y acceso al último PDF

- Cada benchmark nuevo se guarda como una sesión completa con perfil, componentes, resultados y comparación antes/después.
- La vista Benchmark muestra ejecuciones recientes y compara automáticamente contra la última prueba equivalente del mismo PC.
- Se agrega Compatibilidad de sensores usando exclusivamente el snapshot de telemetría ya cargado, sin volver a consultar hardware.
- El diagnóstico indica cobertura real por CPU, RAM, GPU, almacenamiento y batería bajo REAL_OR_NA.
- Después de generar un informe, Diagnóstico conserva accesos para `Abrir último PDF` y `Mostrar carpeta`.
- La ruta del último PDF válido se recuerda entre aperturas de CorePulse mientras el archivo siga existiendo.
- Se preservan el runtime universal canónico y la lógica actual de salud de discos.

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


## V116 — Historial longitudinal de salud
- Cronología diaria de CPU/GPU, salud de almacenamiento, batería e índice del sistema.
- Comparación 7 vs 7 y 30 vs 30 días con deltas observados, sin atribuir causalidad.
- Migración automática de la base SQLite existente; no se pierden muestras previas.
- Se registran además RAM disponible, número de procesos, temperatura máxima de almacenamiento y degradación de batería cuando existen.
- Los análisis manuales de Estabilidad de Windows se reutilizan como snapshots históricos sin volver a consultar eventos al entrar a Historial.
- No se modifica la lógica SMART/NVMe ni el runtime universal.


## V117 — Antes vs Después medido por operación
- Se conserva el historial longitudinal de V116.
- Las sesiones Antes/Después ya no dependen sólo de dos snapshots manuales que se sobrescriben.
- Tweaks de Windows, limpieza RAM segura/profunda, caché y almacenamiento crean una sesión de medición real.
- Se registran CPU, CPU libre, RAM, RAM disponible, procesos, GPU, batería y almacenamiento; FPS/latencia sólo cuando existe una lectura real disponible.
- Las acciones que requieren reinicio quedan como pendientes y CorePulse no inventa un resultado posterior.
- Historial de optimizaciones visible en Centro de Salud > Historial y cambios.
- Diferencias observadas no se presentan como causalidad.
- SMART/NVMe y runtime universal permanecen sin cambios.

## V119 — Recuperación ante fallos
- Se añade marcador de sesión persistente con heartbeat para distinguir cierres normales de cierres bruscos.
- La sesión sólo se marca limpia después de finalizar rollbacks temporales y la verificación final del plan energético.
- El siguiente inicio registra el cierre no limpio, genera un reporte técnico JSON local y expone el estado en Centro de Salud > Recuperación.
- Se amplía Game Boost con rollback persistente de prioridad/Power Throttling por proceso, además del rollback de Windows Game Mode; siempre se valida PID/create-time y se respetan cambios externos.
- Los tweaks persistentes del usuario no se revierten por sorpresa.

## V120 — Centro de Salud inteligente y explicable
- Estado general incorpora una conclusión determinista basada exclusivamente en fuentes reales disponibles.
- Expone cobertura y factores: telemetría, batería, almacenamiento, throttling, estabilidad de Windows y alertas activas.
- Los sensores N/A no reducen artificialmente el estado y no se crea un nuevo porcentaje sintético.

## V121 — Startup Analyzer seguro
- Inicio de Windows se amplía con fabricante, ubicación, estado, impacto y memoria actual cuando existe.
- Se incorporan orígenes Run/RunOnce, carpetas Startup y Win32_StartupCommand.
- Diagnostics-Performance 101 conserva prioridad como evidencia real de impacto alto.
- Deshabilitar sólo está permitido para entradas reversibles del usuario; sistema/seguridad/Microsoft/HKLM permanecen en observación.
- Cada acción tiene backup exacto en AppData y opción Restaurar.

## V122 — SMART NVMe: autoridad de fuente y cero ambiguo
- Se prioriza el Health Log NVMe directo sobre `life_percent`/temperatura consolidados cuando ambas fuentes existen.
- Se corrige el caso donde 0%/0 °C de un proveedor ocultaba un `Percentage Used` y temperatura NVMe válidos.
- `Wear=0` de StorageReliabilityCounter queda cualitativo salvo corroboración/direct SMART; no genera 100% ni un crítico falso.
- Temperatura 0 °C y `TemperatureMax=0` pasan a N/A.
- Centro de Salud ya no convierte un dato SMART no soportado en `Requiere atención inmediata`.

## V135
- Publicación segura desde Centro de Actualizaciones hacia una rama Git de desarrollo.
- Mensaje de commit editable desde CorePulse.
- Protección explícita de `FASE 1`, `FASE 2` y `FASE 3`.
- Bloqueo de publicación directa sobre `main/master/trunk`.
- Generación automática de ZIP + SHA-256 para GitHub Releases después del push.
## V140
- Salud de almacenamiento: `Wear=0` de Windows se valida con actividad real del Reliability Counter (incluidas latencias de E/S) antes de mostrar 100% de vida restante.
- Benchmark: fases GPU reales solamente, transición GPU→CPU/RAM/SSD más clara y volumen SSD probado visible.



## V142 — Diagnóstico Completo 2.0
- `Iniciar diagnóstico` pasa a coordinar una sesión integral: observación en escritorio, estado de Windows/hardware, prueba de estrés y benchmark estándar.
- Prueba de estrés y benchmark permanecen semánticamente separados: estrés evalúa estabilidad bajo carga y no publica una puntuación de rendimiento.
- Windows analiza Inicio, Servicios, Estabilidad y Controladores en segundo plano, sin aplicar reparaciones.
- El benchmark integrado mide CPU, RAM, SSD y GPU sin rankings externos.
- El resultado consolida evidencia en pantalla y el PDF queda como exportación opcional al finalizar.
- Se añaden protecciones térmicas y se conserva REAL_OR_NA.


## V143 — Diagnóstico accionable por componente
- El resultado final del Diagnóstico Completo 2.0 se reorganiza por CPU, GPU, RAM, almacenamiento, batería y Windows.
- Cada tarjeta separa conclusión y evidencia real, sin crear puntuaciones nuevas.
- Se añaden accesos directos al módulo relacionado para revisar el hallazgo.
- Estrés y benchmark permanecen como evidencia interna y dejan de ocupar el protagonismo de la pantalla final.
- PDF y reparaciones siguen siendo opcionales.


## V148
- Mejora de fluidez al redimensionar la ventana mediante un único detector trailing global.
- El Diagnóstico Completo deja de reconfigurar tarjetas en cada evento <Configure>.
- Scroll estable pospone scrollregion/reflow durante resize continuo.
- Gauge de diagnóstico limita repaints de geometría.
- Breakpoints 3/2/1 columnas para distintas dimensiones.

## V149
- Diagnóstico Completo: evidencia trazable por componente dentro de la misma pantalla.
- CPU/GPU/RAM separan escritorio, estrés y benchmark.
- Almacenamiento separa salud física de rendimiento SSD.
- Batería y Windows muestran sus fuentes/mediciones disponibles sin inventar faltantes.
- Acciones separadas: `Ver evidencia` vs. abrir módulo especializado.
- PDF reutiliza la misma estructura de evidencia detallada.


## V150
- Se cierra Diagnóstico Completo 3.0.
- Botón Cancelar con detención cooperativa e invalidación de callbacks antiguos.
- Registro de estado/duración por fase y cobertura final.
- Comparación contra el diagnóstico anterior sin contaminar el diagnóstico actual.
- Evidencia y PDF sincronizados.

## V151
- Hotfix de cancelación: `Diagnosticar de nuevo` queda visible y funcional sin reiniciar CorePulse.
- Publicación Git: una versión anterior registrada en HEAD pero ya eliminada localmente se trata como reemplazo esperado, no como bloqueo.
- Las modificaciones reales dentro de una versión anterior continúan bloqueando la publicación para evitar pérdida de trabajo.
- Actualizaciones/Publicar recupera una densidad compacta y acciones visibles en ventanas de distinta altura.

## V152
- Hotfix de publicación cuando `CorePulse_V152` ya existe localmente.
- Reutiliza el destino sólo si coincide exactamente con la versión ejecutada; si difiere, bloquea para proteger cambios locales.
- Validación end-to-end V136 -> V152 con FASE 1/2/3 intactas.
- Corrección visual en Publicar: el registro usa el área flexible y se elimina el hueco inferior artificial.

## V153
- Hotfix de publicación para destinos locales no rastreados que difieren de la versión en ejecución.
- Respaldo persistente antes de sincronizar la carpeta destino.
- Mensajes de Publicar más claros para este estado.

### V154
- Rediseño de arquitectura y lenguaje de Publicar: repositorio local → origin → rama destino → carpeta CorePulse.
- El nombre/ruta del checkout local ya no se confunde con la carpeta `CorePulse_Vxxx` ni se asume una ruta de Maxi/Tomás.
- Publicación de rama desacoplada de GitHub Releases.
- Respaldo de carpeta local corregido.

## V155
- Publicador Git simplificado y robusto para reemplazo de versiones CorePulse sin perder copias locales.
- Las carpetas CorePulse antiguas dejan de bloquear por modificaciones: se conservan en disco y sólo se eliminan del índice/commit remoto.
- Respaldo reversible de la carpeta V155 si ya existe y difiere.
- Rama y URL remota visibles en la acción de publicación.


## V163
- Optimización de vistas ocultas y carga perezosa de Red/Conectividad.
- Endurecimiento de planes de energía para reutilizar la misma copia y evitar duplicados acumulativos.
- Menos escrituras redundantes en Test de Audio y limpieza visual interna.
- Benchmark/Diagnóstico/Overlay conservan la metodología de V162.
