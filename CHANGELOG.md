## V0.10.0.0w — Health Intelligence & Recovery

- Centro de Salud integrado en Diagnóstico.
- Battery Health con capacidad de diseño/actual, desgaste, ciclos, carga y autonomía real cuando Windows la expone.
- Thermal Throttling Detector con estados CONFIRMED/SUSPECTED/WATCHING y evidencia.
- Benchmark corto de CPU, RAM y SSD; GPU mediante WinSAT D3D cuando está disponible.
- Historial SQLite de salud y benchmarks.
- Capturas Antes vs Después con deltas observados.
- Startup Analyzer con Win32_StartupCommand y eventos Diagnostics-Performance 101.
- Services Analyzer sin desactivación automática.
- Crash Analyzer para BSOD, WHEA, Kernel-Power, Application Error/Hang y apagados inesperados.
- Driver Health con firma, proveedor, versión y antigüedad.
- Hardware Changes con baseline persistente.
- Restore/Rollback mediante Checkpoint-Computer y rollback existente de Tweaks.
- Network Diagnostics reutiliza Red avanzada existente.

## V0.9.24.15w — Python 3.12+ Compatibility

- Runtime compatible por política con Python x64 3.12 o superior, sin límite máximo artificial.
- Instalador detecta automáticamente un Python moderno, crea `.venv` y usa ese intérprete.
- Dependencias base y stack de sensores profundos separados para que una incompatibilidad futura de `pythonnet` no bloquee el arranque completo.
- `requirements-sensors.txt` se instala en modo best-effort; CorePulse conserva `REAL_OR_NA` si el bridge no está disponible.
- `pyproject.toml` declara `requires-python = ">=3.12"`.
- Comprobador de requisitos actualizado a política 3.12+.

## V0.9.24.15w — Professional Render & Hover Polish

## V0.9.24.15w — Trends Flicker Elimination

- Elimina `FigureCanvasTkAgg` de la vista **Tendencias** para evitar flashes del canvas Tk al entrar/salir de la pestaña.
- El gráfico se rasteriza fuera de pantalla con `FigureCanvasAgg` y se publica como una imagen terminada.
- Tendencias conserva una única superficie gráfica persistente; ya no destruye/recrea el canvas de Matplotlib en cada `render()`.
- Añade una firma de datos para omitir repintados completos cuando sesiones/resumen no cambiaron.
- Mantiene scroll, tema claro/oscuro, Session Accuracy y `REAL_OR_NA` sin cambios funcionales.

- Elimina el loader a pantalla completa entre vistas: la página actual permanece visible hasta que la siguiente está lista.
- Reduce parpadeos al volver al Dashboard y limita el repintado visible de Matplotlib.
- Normaliza radios de tarjetas/botones en modo claro para evitar esquinas recortadas bajo escalado DPI.
- Refuerza el contraste de hover en navegación y controles del modo claro.
- Corrige el hover de tarjetas navegables al cruzar entre widgets hijos.
- Añade feedback hover a las filas de Tweaks Windows 11.
- Mantiene modo oscuro, telemetría, REAL_OR_NA y Global Scroll Engine V2 sin cambios funcionales.

## V0.9.24.12w — Agent Instant Reaction & Sustained Alert Separation

- El Agente CorePulse reacciona inmediatamente a condiciones ELEVATED/WARNING/CRITICAL sin confundirlas con alertas sostenidas.
- La tarjeta cambia a **OBSERVANDO** o **REACCIONANDO**, adopta color ámbar/rojo y muestra la causa real mientras confirma persistencia.
- Las alertas sostenidas conservan el motor Rolling Evidence y siguen requiriendo evidencia temporal antes de activarse.
- El estado del agente incluye una evaluación instantánea derivada de la misma política térmica real del Dashboard.
- Alertas y diagnóstico muestra las condiciones instantáneas como **en observación** en lugar de afirmar falsamente que no ocurre nada.
- No se añaden sensores, temperaturas ni alertas sintéticas; se mantiene REAL_OR_NA.

## V0.9.24.10w — CPU Sensor Inventory Reliability Fix

- Corrige el `TypeError` que impedía renderizar las filas de sensores CPU pese a que el pipeline sí había detectado el inventario.
- Corrige el mismo fallo latente en el ordenamiento de sensores GPU.
- Añade fallback de métricas CPU reales desde el snapshot certificado cuando el hardware no expone inventario LHM.
- Los errores de refresco CPU/GPU dejan de silenciarse y se registran con throttling.
- Mantiene REAL_OR_NA: ausencia física de un sensor continúa mostrándose como N/A.

## V0.9.24.10w — Network Upload Accuracy Fix

- Corrige el cálculo de subida del Speed Test: `Server-Timing` ya no se usa como duración de transferencia.
- El tiempo de servidor se resta de la duración de petición cuando es válido, siguiendo la semántica documentada por Cloudflare.
- Los streams paralelos se agregan mediante bytes totales / tiempo real de etapa para evitar doble contabilización.
- CorePulse valida descarga/subida contra la velocidad física negociada del adaptador y descarta resultados imposibles.
- La interfaz muestra `N/A` y una advertencia si una medición supera el techo físico del enlace en vez de certificarla como válida.


## V0.9.24.8w — Header & Sidebar Layout Refresh

- Mueve el símbolo de CorePulse desde el sidebar a la cabecera principal.
- El sidebar queda dedicado a navegación, agente, selector de tema y versión.
- Alinea el logo con la identidad real del equipo monitoreado.
- Recupera altura útil para que Agente CorePulse no quede comprimido.
- Mantiene el mismo layout en modo claro y oscuro.
- Conserva Global Scroll Engine V2, telemetría, Tweaks y Red avanzada sin cambios funcionales.

## V0.9.24.6w — Light Theme Polish & Sidebar Balance
- Corrige superficies internas que permanecían oscuras en modo claro (RAM, Alertas, Tweaks, Red y vistas históricas).
- Hace que los gráficos de Tendencias respeten la paleta clara, incluyendo fondo, leyenda y grilla.
- Construye páginas internas fuera del viewport y las publica de forma atómica para impedir que widgets parciales atraviesen el loader.
- Reduce y recentra el símbolo superior de CorePulse para recuperar espacio vertical del sidebar.
- Amplía y equilibra la tarjeta del Agente CorePulse para que el detalle no quede recortado junto al selector de tema.

## V0.9.24.5w — Global Scroll Engine V2

- Reemplaza el desplazamiento basado en `Canvas.create_window` por un viewport nativo con clipping real.
- Agrupa eventos de rueda/touchpad a ~60 FPS para evitar ghosting y trails de CustomTkinter en Windows.
- Mantiene la API `StableScrollHost` para CPU, GPU, RAM, Red, Tweaks, alertas, historial y tendencias.
- Conserva repintados diferidos durante la inercia y el estado real de telemetría.

## V0.9.24.3w — Global UI & Scroll Stability

- Sustituye el scroll privado de CustomTkinter por `StableScrollHost` en todas las páginas internas grandes.
- Canvas sólido, routing de rueda por puntero, scrollbar propio, inercia y scrollregion con debounce.
- CPU/GPU/RAM/Red conservan telemetría superior en vivo y difieren el repintado del cuerpo durante scroll.
- Tweaks aplaza la actualización masiva de 66 estados hasta que termina el desplazamiento.
- Alertas, historial y tendencias aplazan reconstrucciones cuando el usuario está desplazando su contenido.
- La navegación muestra una capa opaca mientras se construye cada página, eliminando frames parciales o transparentes durante la entrada.
- Al regresar al Resumen, CorePulse fuerza el repintado de TkAgg antes/después de retirar la vista interna para evitar zonas blancas en los gráficos.
- Sin cambios en telemetría, `REAL_OR_NA`, Speed Test, Tweaks ni reglas de diagnóstico.

## V0.9.24.2w — Real Internet Speed Test

- Separa claramente **tráfico instantáneo** de **capacidad de Internet**.
- Añade prueba activa de descarga/subida en Mbps contra `speed.cloudflare.com`.
- Ramp-up con 4 flujos paralelos para saturar mejor conexiones rápidas, con parada adaptativa por duración.
- Añade ping y jitter sin carga, servidor/edge de medición, duración y MB transferidos.
- La prueba corre fuera del hilo Tk y nunca se ejecuta automáticamente: sólo mediante acción explícita del usuario.
- Mantiene `REAL_OR_NA`: si una fase falla se muestra N/A, no se estima.

# Changelog CorePulse


## V0.9.24.1w — Network Sidebar Fix

- Corrige la navegación lateral profesional: **Red avanzada** ahora permanece visible después de reconstruir el Dashboard.
- Integra el botón en iconos, layout responsivo, estado activo y dispatcher de navegación.
- Añade icono de red consistente con el resto del sidebar.
- No modifica la lógica de telemetría ni diagnóstico de red de V0.9.24.0w.

## V0.9.24.0w — Network Advanced Details

- Nueva página interna de red con información del adaptador principal y todos los adaptadores detectados.
- Inventario combinado `psutil` + `Get-NetAdapter` / `Get-NetIPConfiguration`; `netsh wlan` añade datos Wi-Fi cuando existen.
- Tasas de descarga/subida calculadas sólo desde deltas de contadores reales, sin test sintético de velocidad.
- Contadores de tráfico, paquetes, errores y drops por interfaz.
- Diagnóstico manual de gateway, Internet y DNS en worker dedicado, con latencia y pérdida ICMP reales.
- La navegación y el panel aplican la misma protección de scroll usada por CPU/GPU/RAM.
- Política `REAL_OR_NA` preservada para toda la capa de red.

## V0.9.23.1w — Extended Windows Tweaks

- Catálogo ampliado a 66 ajustes, con 11 categorías y seis presets.
- Presets automáticos limitados a cambios Bajo/Medio; ningún tweak Alto/Crítico puede entrar en un preset.
- Metadata visible de ADMIN, EXPLORER y REINICIO por tweak.
- Doble confirmación para cambios críticos y verificación de privilegios antes de ejecutar.
- Motor híbrido: respaldo exacto de Registro + acciones PowerShell/WinGet con reversión declarada.
- Desinstalación opcional de Edge conservando WebView2, OneDrive sin borrar la carpeta personal y Windows Web Experience/Widgets.
- Seguridad avanzada: Defender, SmartScreen, UAC, HVCI y VBS, siempre manuales y fuera de presets.
- Tweaks adicionales para privacidad, Explorer, barra de tareas, rendimiento, gaming, energía, red y Windows Update.
- CorePulse continúa sin descargar ni ejecutar scripts remotos.

## V0.9.23.0w — Windows 11 Tweaks

- El sidebar deja sólo el símbolo de CorePulse en el encabezado.
- Nueva vista interna de Tweaks para Windows 11.
- Motor declarativo y reversible con respaldo del valor previo antes de cada cambio.
- Presets Minimal, Recomendado, Privacidad y Gaming.
- Detección de tweaks aplicados, aplicación/deshacer por selección y reinicio opcional de Explorer.
- Punto de restauración opcional si CorePulse se ejecuta como administrador.
- No descarga ni ejecuta scripts externos y excluye cambios de Defender/Windows Update.

## V0.9.22.0w — RAM Advanced Details

### Añadido
- Nueva vista interna **Memoria RAM** con diseño consistente con CPU/GPU Advanced Details.
- Tarjeta RAM navegable y botón `Ver detalles` idéntico al resto del Dashboard.
- Resumen en tiempo real de uso físico, memoria utilizada, disponible y total utilizable.
- Inventario de módulos mediante `Win32_PhysicalMemory`.
- Conteo de slots mediante `Win32_PhysicalMemoryArray`.
- Detalle por módulo: slot/banco, capacidad, fabricante, part number, tipo SMBIOS, form factor, velocidad configurada/reportada, ancho de datos/total y voltaje configurado cuando existe.
- Protección de repintado durante scroll y carga de inventario en hilo separado.

### Integridad
- Capacidad instalada y total utilizable se presentan como conceptos distintos.
- Slots disponibles se derivan sólo de `MemoryDevices - módulos detectados` y se rotulan como dato derivado de inventario real.
- No se infieren canal Single/Dual, timings CAS ni perfiles XMP/EXPO.
- Se mantiene `REAL_OR_NA`.

## V0.9.21.1w — GPU Data Consistency

### Corregido
- Prioridad visual para VRAM total certificada por LibreHardwareMonitor frente al campo de inventario `AdapterRAM` de WMI.
- Los valores WMI limitados alrededor de 4 GB se identifican explícitamente cuando contradicen un sensor real de mayor capacidad.
- Estado del dispositivo Windows humanizado (`OK` → `Funcionando correctamente`).
- Resolución y refresco distinguen ausencia de dato de una pantalla activa asociada a otro adaptador del sistema.
- Tipos internos como `GpuNvidia` se convierten a etiquetas de familia de sensores legibles.
- Nombres de fuente normalizados para la interfaz.

### Integridad
- `Win32_VideoController.AdapterRAM` permanece visible como dato de inventario y nunca sustituye un total de VRAM real de sensor cuando éste existe.
- No se infiere que una GPU sea integrada o dedicada por marca/nombre.
- Se mantiene `REAL_OR_NA`.

## V0.9.21.0w — GPU Advanced Details

### Añadido
- Vista interna **Detalles avanzados de GPU** desde el Dashboard.
- Selector multi-GPU con identidad separada por adaptador.
- Resumen en tiempo real de uso, temperatura, VRAM y potencia.
- Identidad/controlador desde Win32_VideoController: fabricante reportado, procesador de vídeo, versión del driver, estado, resolución, refresco y PNP Device ID cuando existen.
- Inventario de sensores GPU de LibreHardwareMonitor, incluyendo temperatura, hotspot, clocks, cargas, memoria, potencia, ventilador, control y voltaje cuando están expuestos.
- Nuevas métricas certificadas `fan_rpm`, `fan_control_percent` y `core_voltage_v`.
- Protección de repintado durante scroll equivalente a la vista CPU.

### Integridad
- La GPU inicial se selecciona por actividad real mediante la política universal existente, no por marca.
- Adaptadores detectados sólo por Windows permanecen visibles como inventario y sus sensores continúan en `N/A`.
- No se deriva VRAM utilizada desde porcentajes ni se estiman clocks, potencia, ventilador o voltaje.
- Se mantiene la política `REAL_OR_NA`.

## V0.9.20.3w — Button Visual Consistency

- Unifica el estilo del botón **Ver detalles** de las unidades de almacenamiento con el botón CPU del Dashboard.
- Mismo tamaño, borde, colores, hover y tipografía para mantener consistencia visual.
- Conserva la navegación y la lógica existente del detalle de almacenamiento.

## V0.9.20.2w — CPU Scroll & UI Polish

- Corregido el ghosting/repintado defectuoso observado en Windows al desplazar la vista CPU mientras se actualizaban decenas de sensores.
- Nuevo observador de viewport: pausa únicamente el repintado de widgets dentro del canvas durante scroll e inercia; las tarjetas superiores siguen en tiempo real.
- Sensores CPU ordenados de forma estable para reducir cambios de layout.
- `Ver detalles` ahora es un botón CorePulse real, sin flecha, con borde/hover coherentes con el Dashboard.
- `Volver al resumen` ahora usa estilo de acción secundaria CorePulse y elimina la flecha decorativa.
- Las tarjetas clickeables ya no enlazan recursivamente el clic de `CTkButton`, evitando dobles aperturas.
- Mantiene política `REAL_OR_NA`; no se modificó la autoridad de telemetría ni diagnóstico.

## V0.9.20.1w — CPU Advanced Details Fixes

### Corregido
- El pipeline certificado conserva el inventario individual de sensores CPU de LibreHardwareMonitor (`sensors` + `sensor_count`).
- Restauradas en la capa certificada las lecturas CPU avanzadas de carga total, bus clock y voltaje cuando existen.
- La frecuencia WMI deja de presentarse como turbo máximo y se identifica como frecuencia nominal reportada por Windows.
- Frescura y hora de lectura en Trazabilidad usan el timestamp del sensor y fallback al snapshot certificado, evitando `N/A` en métricas válidas.
- El panel del agente diferencia monitoreo activo de alertas sostenidas y elimina la etiqueta visual `ESTADO: NORMAL`.
- Entrada a Detalles de CPU con transición de carga limpia para evitar solapamiento de vistas.
- Estado instantáneo `TEMPERATURA CRÍTICA` cuando la evidencia térmica real llega a nivel crítico, incluida distancia a TjMax ≤ 5 °C.
- La distancia a TjMax usa semántica visual inversa: un margen pequeño se resalta como riesgo y no como “temperatura baja”.
- Capacidades de virtualización rotuladas explícitamente como información reportada por Windows.

### Integridad
- Se conserva `REAL_OR_NA`; el fallback visual de sensores sólo reutiliza valores reales ya presentes y certificados en el snapshot.
- Se preservan timestamps originales de sensores; no se retimbran lecturas cacheadas como nuevas.

## V0.9.20.0w — CPU Advanced Details

### Añadido
- Nueva vista interna **Detalles avanzados de CPU** accesible desde la tarjeta CPU del Dashboard.
- Especificaciones reales de CPU desde Windows/CIM: fabricante, socket, arquitectura, núcleos, hilos, cachés L2/L3, frecuencia reportada y capacidades de virtualización.
- Inventario dinámico de sensores CPU de LibreHardwareMonitor: temperatura, carga, reloj, potencia y voltaje cuando estén disponibles.
- Resumen en tiempo real de uso, temperatura, frecuencia y potencia del paquete.
- Tabla de sensores con nombre, tipo, valor y origen, actualizada desde el snapshot vigente sin bloquear la interfaz.

### Interfaz
- La tarjeta CPU ahora es navegable y muestra la acción `Ver detalles`.
- La vista avanzada mantiene la identidad visual del Dashboard y permite volver al Resumen sin abrir ventanas externas.
- Las lecturas ausentes se muestran explícitamente como `N/A`.

### Integridad
- Se conserva la política `REAL_OR_NA`: CorePulse no inventa TDP, voltajes, temperaturas, clocks ni capacidades no expuestas por Windows/LHM.
- La página avanzada consume el snapshot de telemetría existente; no realiza sondeos de sensores desde el hilo de Tkinter.
- Los datos estáticos de Windows se cargan fuera del hilo de UI.

## V0.9.19.1w — UI & Diagnostic Consistency

### Mejorado
- Separación visual entre estado instantáneo y alertas sostenidas.
- Nuevo estado `ATENCIÓN TÉRMICA` para temperaturas elevadas que aún no constituyen una alerta sostenida.
- Trazabilidad de telemetría rediseñada con inspector de métrica, nomenclatura en español y feedback de frescura.
- Cobertura del Dashboard expresada como métricas `VÁLIDAS`.
- Antigüedad real del snapshot en “Última actualización”.
- Feedback hover en tarjetas superiores realmente navegables.
- Énfasis térmico de CPU/GPU y lectura contextual en detalles de almacenamiento.

### Integridad
- No se agregan sensores sintéticos ni valores estimados.
- `REAL_OR_NA` y `REAL_FPS_OR_NA_ONLY` permanecen sin cambios.
- La condición instantánea no se presenta como una alerta sostenida hasta que el agente temporal lo confirme.

## V0.9.19.0w

### Añadido
- Vista interna de trazabilidad de telemetría.
- Metadata visible de fuente, sensor, calidad y frescura por métrica.
- Estado del proveedor y del worker de telemetría.
- Logging rotativo de ejecución y hooks para excepciones no controladas.
- Redacción preventiva de secretos en logs.

### Mejorado
- Los errores repetitivos de telemetría y renderizado dejan de desaparecer silenciosamente y se registran con throttling.
- La tarjeta `COBERTURA DE TELEMETRÍA` ahora abre el detalle de las lecturas certificadas.

### Conservado
- Política `REAL_OR_NA`.
- Política `REAL_FPS_OR_NA_ONLY`.
- Detección universal por hardware real en tiempo de ejecución.
- Separación entre salud técnica, vigencia anual e IA explicativa.
