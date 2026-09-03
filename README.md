# CorePulse V0.10.0.0w

## Python 3.12+

CorePulse V0.10.0.0w mantiene compatibilidad Python 3.12+ y añade el Centro de Salud avanzado. El runtime acepta CPython x64 3.12 o cualquier versión posterior sin un límite superior artificial. Usa `instalar_dependencias.bat`, que crea `.venv` con el intérprete compatible detectado.

Las dependencias de sensores profundos (`pythonnet` + `HardwareMonitor`) se instalan como un bloque opcional de mejor esfuerzo. Si una versión futura de Python todavía no tiene wheel compatible, CorePulse arranca con las fuentes disponibles y mantiene `REAL_OR_NA`; las métricas dependientes de LibreHardwareMonitor pueden quedar en `N/A` hasta que el proveedor publique soporte.

Archivos de entorno:
- `requirements-base.txt`: runtime obligatorio.
- `requirements-sensors.txt`: puente opcional de sensores profundos.
- `requirements.txt`: instala la base.
- `Iniciar_CorePulse.bat`: ejecuta el `.venv` creado por el instalador.


## Centro de Salud V0.10.0.0w

Nueva vista integrada con Battery Health, detector de throttling basado en evidencia, benchmarks cortos CPU/GPU/RAM/SSD, historial longitudinal de salud, capturas Antes/Después, Startup Analyzer, Services Analyzer, Crash/BSOD/WHEA Analyzer, Driver Health, cambios de hardware y creación explícita de puntos de restauración. Red avanzada se reutiliza como Network Diagnostics.

Reglas: REAL_OR_NA, ninguna desactivación automática de servicios críticos, throttling confirmado sólo con sensor explícito y rollback/restauración bajo acción del usuario.

## Tendencias sin parpadeo V0.9.24.15w

La vista Tendencias usa renderizado off-screen con Matplotlib Agg y una superficie de imagen persistente para evitar flashes de TkAgg durante navegación y refrescos.


## Professional Render & Hover Polish

Revisión global de renderizado claro, navegación atómica sin flashes y feedback hover consistente.


> Tema claro/oscuro unificado: usa el botón del sidebar; CorePulse recuerda tu elección.

> Esta build incorpora **Global Scroll Engine V2**, sin `Canvas.create_window` para páginas grandes, para corregir ghosting durante scroll rápido en Windows.

CorePulse es una aplicación de escritorio para Windows 10/11 x64 orientada al monitoreo, diagnóstico, optimización guiada y documentación técnica de **cualquier PC o notebook compatible con las fuentes de hardware disponibles**. La arquitectura no contiene reglas de ejecución amarradas a un modelo, fabricante o equipo de prueba concreto.



## Novedades V0.9.24.15w

### Light Comfort

El modo claro usa ahora superficies gris azuladas, sin blancos puros, con bordes de mayor contraste para reducir fatiga visual y mejorar la definición de las tarjetas.


- **Agent Instant Reaction:** el Agente CorePulse cambia a OBSERVANDO/REACCIONANDO ante una condición térmica instantánea mientras confirma persistencia.
- Diferencia visualmente **condición instantánea** de **alerta sostenida**; una no se presenta como la otra.
- Alertas y diagnóstico también muestra la condición provisional en observación sin escribirla en el historial como alerta confirmada.
- **CPU Sensor Inventory Reliability:** corrige la tabla vacía de sensores y añade fallback desde métricas reales certificadas.
- **GPU sensor sort fix:** elimina el mismo fallo latente en la vista GPU.

- Logo trasladado desde el sidebar a la cabecera principal.
- Sidebar más compacto, con navegación desde la parte superior.
- Bloque Agente CorePulse con mayor altura útil y detalle siempre visible.
- Selector Claro/Oscuro y versión alineados con el bloque del agente.

## Base heredada de V0.9.24.6w

- Modo claro corregido en todas las superficies internas: sin paneles azul marino heredados del tema oscuro.
- Tendencias/Matplotlib usan fondo, leyenda y grilla coherentes con el tema activo.
- Las páginas internas se construyen fuera de pantalla y se publican de una sola vez para evitar widgets parciales sobre el loader.
- Logo superior reducido y recentrado para recuperar espacio vertical del sidebar.
- Tarjeta del Agente CorePulse ampliada y alineada con el botón de tema y la versión.
- Conserva Global Scroll Engine V2, telemetría, REAL_OR_NA, Tweaks y Red avanzada.

## Novedades V0.9.24.2w

- Prueba de velocidad activa de Internet (descarga, subida, ping y jitter) usando endpoints públicos de Cloudflare Speed Test.
- Tráfico actual y capacidad de Internet quedan visualmente separados para evitar confusiones.

- Nueva vista interna **Red avanzada** integrada al sidebar de CorePulse.
- Inventario de adaptadores con estado, descripción, MAC, IPv4/IPv6, gateway, DNS y velocidad de enlace cuando Windows los expone.
- Datos Wi-Fi reales: SSID, BSSID, señal, radio, canal y tasas negociadas cuando `netsh wlan` los publica.
- Tráfico real por adaptador con descarga/subida actual calculada exclusivamente desde deltas de `psutil.net_io_counters`.
- Contadores acumulados de bytes, paquetes, errores y descartes.
- Diagnóstico bajo demanda separado en gateway, salida a Internet y resolución DNS, ejecutado fuera del hilo gráfico.
- Soporte de pérdida y latencia ICMP sin interpretar un gateway que bloquee ping como caída automática de Internet.
- Actualización de identidad en segundo plano y protección contra ghosting durante scroll.
- Se mantiene `REAL_OR_NA`: no se inventan DNS, gateways, SSID, señal, velocidad, latencia ni conectividad.

## Novedades V0.9.23.1w

- Biblioteca ampliada a **66 tweaks de Windows 11** organizados en Explorador, Barra de tareas, Interfaz, Privacidad, Gaming, Energía, Sistema, Actualizaciones, Red, Apps/debloat y Seguridad avanzada.
- Nuevos presets **Rendimiento** y **Avanzado seguro**, además de Minimal, Recomendado, Privacidad y Gaming.
- Los ajustes de riesgo Alto/Crítico nunca forman parte de presets automáticos.
- Confirmación doble para cambios críticos y bloqueo cuando se requieren privilegios de administrador.
- Nuevos ajustes de Explorer, interfaz, telemetría/privacidad, Game DVR, HAGS, power throttling, hibernación, Fast Startup, Windows Update, LLMNR y políticas de Edge.
- Acciones avanzadas para desinstalar **Microsoft Edge** (manteniendo WebView2), OneDrive y Windows Web Experience/Widgets, con método de reversión definido.
- Sección **Seguridad avanzada** para Defender, SmartScreen, UAC, HVCI y VBS; siempre fuera de presets y claramente marcada como alto impacto.
- El motor distingue **deshacer exacto** de cambios de Registro y **reversión definida** de acciones de sistema/WinGet.
- Se mantiene la regla de no ejecutar scripts remotos (`irm | iex` / Invoke-Expression).

## Novedades V0.9.23.0w

- Branding lateral minimalista: el encabezado del sidebar muestra sólo el símbolo de CorePulse.
- Nueva pestaña **Tweaks Windows 11** integrada a la navegación interna.
- Presets Minimal, Recomendado, Privacidad y Gaming.
- Detección best-effort del estado actual de cada tweak.
- Aplicación reversible: CorePulse guarda el valor previo del Registro por usuario/equipo.
- Acción **Deshacer seleccionados** que restaura únicamente estados guardados por CorePulse.
- Punto de restauración opcional cuando hay privilegios de administrador.
- Reinicio manual de Explorer para cambios que lo requieren.
- Sin scripts remotos: la pestaña no ejecuta `irm | iex`.

## Novedades V0.9.22.0w

- Nueva vista interna **RAM Advanced Details** accesible desde la tarjeta MEMORIA RAM del Dashboard.
- Resumen vivo de uso, memoria en uso, disponible y total utilizable por Windows.
- Inventario real de módulos desde `Win32_PhysicalMemory`: slot, banco, fabricante, part number, capacidad, tipo SMBIOS, formato, velocidades reportadas, ancho de datos y voltaje cuando existen.
- Conteo de slots desde `Win32_PhysicalMemoryArray`, con slots disponibles derivados únicamente de contadores WMI reales.
- Diferencia explícita entre **capacidad instalada** y **memoria utilizable por Windows**, evitando interpretar memoria reservada como un fallo.
- La consulta Windows/SMBIOS se realiza fuera del hilo gráfico; la vista consume el snapshot existente para telemetría y mantiene protección de scroll.
- Canal Single/Dual, timings CAS y XMP/EXPO permanecen en `N/A` cuando Windows no los expone de forma universal.
- La tarjeta RAM adopta el mismo botón **Ver detalles** que CPU, GPU y almacenamiento.
- Se mantiene `REAL_OR_NA`: no se inventan slots, velocidades, voltajes, canales ni timings.

## Novedades V0.9.21.1w

- La VRAM total de sensor real tiene prioridad visual sobre `Win32_VideoController.AdapterRAM`.
- Si WMI devuelve ~4 GB para una GPU cuyo sensor real expone más de 4 GB, el dato se conserva como inventario pero se rotula **limitado por WMI**.
- `Estado Windows: OK` se humaniza como **Funcionando correctamente**.
- Resolución y frecuencia distinguen `N/A` de una pantalla activa asociada a otro adaptador en configuraciones multi-GPU.
- `GpuNvidia` / `GpuAmd` / `GpuIntel` dejan de mostrarse como nombres internos y se presentan como familia de sensores legible.
- Las fuentes `LibreHardwareMonitorLib` se muestran al usuario como **LibreHardwareMonitor**.
- Se conserva `REAL_OR_NA`: la corrección cambia interpretación/presentación, no inventa VRAM, pantalla, clocks ni sensores.

## Novedades V0.9.21.0w

- Nueva vista interna **Detalles avanzados de GPU** accesible desde la tarjeta GPU del Dashboard.
- Soporte multi-GPU: cada adaptador mantiene identidad, controlador, VRAM y sensores separados.
- Selección inicial de GPU basada en actividad real del snapshot, nunca en fabricante.
- Resumen vivo de uso, temperatura, VRAM y potencia cuando los sensores existen.
- Identidad Windows: fabricante reportado, procesador de vídeo, driver, estado, resolución, refresco y PNP ID.
- Lecturas avanzadas: hotspot, clocks, carga de memoria, VRAM usada/total, ventilador, control, voltaje y potencia cuando LHM los expone.
- Tabla completa de sensores GPU reales con tipo, valor, origen y frescura.
- La vista GPU hereda la protección de scroll de CPU para evitar ghosting durante actualizaciones.
- Se conserva `REAL_OR_NA`: una GPU sin telemetría puede aparecer por inventario, pero sus sensores siguen en `N/A`.

## Novedades V0.9.20.1w

- Corrección del inventario de **sensores CPU visibles**: la capa certificada conserva ahora las lecturas individuales reales de LibreHardwareMonitor que ya alimentan temperatura, clocks, carga, potencia y voltaje.
- La frecuencia `Win32_Processor.MaxClockSpeed` se presenta como **Frecuencia nominal (Windows)** y queda separada del **máximo observado** por telemetría, evitando confundirla con el turbo máximo real.
- La vista de **Trazabilidad de telemetría** usa primero el timestamp real del sensor y, cuando no existe, la marca del snapshot certificado; las métricas válidas ya no quedan visualmente con frescura `N/A`.
- El panel lateral del agente deja de mostrar `ESTADO: NORMAL` durante una condición térmica instantánea: ahora informa `MONITOREANDO` y el estado de **alertas sostenidas** por separado.
- Nueva transición limpia `Cargando información del procesador…` al entrar en Detalles de CPU para evitar solapamientos entre Dashboard y vista interna.
- Si la CPU queda a **≤ 5 °C de TjMax** o alcanza el umbral térmico crítico certificado, el estado instantáneo se identifica como **TEMPERATURA CRÍTICA**.
- Las capacidades de virtualización se rotulan explícitamente como datos reportados por Windows.
- Se conserva la política `REAL_OR_NA`: ninguna corrección introduce sensores, timestamps, TDP, voltajes, clocks o temperaturas sintéticas.

## Principios de integridad

CorePulse aplica dos contratos centrales:

- `REAL_OR_NA`: una métrica de hardware solo se muestra si proviene de una fuente real. Si no existe una lectura válida, se informa `N/A` / `No disponible`.
- `REAL_FPS_OR_NA_ONLY`: FPS y frametime no se simulan ni estiman. Se muestran únicamente cuando existe una fuente real certificada.

La IA no reemplaza sensores, SMART ni telemetría. Su función es interpretar el diagnóstico ya certificado por CorePulse, investigar evidencia externa verificable y ayudar a explicar acciones seguras.

## Funciones del producto

- Identificación dinámica del equipo: fabricante/modelo exacto en notebook; en PC de escritorio se muestra la plataforma y la placa madre cuando esa es la identidad útil disponible.
- Inventario de BIOS, CPU, todas las GPU detectadas, módulos/capacidad RAM y unidades de almacenamiento.
- Telemetría real de uso, frecuencias, temperaturas, capacidad, SMART/salud y otras métricas cuando el proveedor las expone.
- Monitoreo continuo y diagnóstico por sesión con evidencia temporal.
- Alertas, historial y tendencias.
- Overlay de juegos/programas mediante RTSS y FPS reales mediante PresentMon.
- Limpieza por módulos separados: caché, memoria, archivos duplicados y almacenamiento.
- Generación de PDF después del período de diagnóstico, con ubicación elegida por el usuario y apertura automática.
- Vigencia anual del hardware separada de la salud técnica.
- Plan de acción para problemas confirmados, con pasos, precauciones e insumos.
- Investigación de tutoriales de YouTube exactos para la plataforma/modelo y acción requerida, solo cuando pueden verificarse; si no, CorePulse lo informa sin inventar enlaces.
- Agente en tiempo real y bandeja del sistema al minimizar la aplicación.

## Universalidad de hardware

“Universal” en este proyecto significa que la lógica de CorePulse se construye a partir del **hardware detectado en tiempo de ejecución**, no desde listas de modelos concretos. La aplicación puede usar proveedores especializados cuando estén disponibles, pero ninguna marca tiene prioridad funcional sobre otra. La selección de GPU representativa usa actividad/telemetría real y el inventario conserva todas las GPU encontradas.

La compatibilidad final debe validarse en múltiples arquitecturas, fabricantes, equipos portátiles/escritorio y configuraciones multi-GPU/multi-almacenamiento. Un test exitoso en un equipo no se presenta como certificación de todos los equipos.

## Requisitos

- Windows 10/11 x64.
- Python x64 3.12 o superior recomendado para desarrollo; sin tope artificial de versión.
- Dependencias de `requirements.txt`.
- PresentMon incluido en `tools/presentmon/PresentMon.exe`.
- RTSS instalado para mostrar el overlay en juegos.
- Algunos sensores de bajo nivel pueden requerir permisos de administrador y el proveedor compatible instalado.

## Instalación para desarrollo

1. Ejecuta `instalar_dependencias.bat` o instala manualmente:

   ```powershell
   python -m pip install -r requirements.txt
   ```

2. Si usarás IA, crea tu configuración privada:

   ```powershell
   Copy-Item .\.env.example .\.env
   ```

3. Agrega tu propia `GROQ_API_KEY` en `.env`. No la subas al repositorio ni la compartas.
4. Inicia CorePulse:

   ```powershell
   python .\main.py
   ```

## Estructura principal

```text
CorePulse/
├── main.py
├── core/                 # telemetría, identidad, diagnóstico, IA, PDF y servicios
├── gui/                  # interfaz gráfica
├── database/             # persistencia local
├── assets/               # branding e iconos
├── tools/presentmon/     # proveedor de FPS reales
├── data/                 # datos generados en ejecución
├── logs/                 # registros de ejecución
├── tests/                # pruebas estables y diagnósticos manuales
├── ARQUITECTURA.md
├── requirements.txt
├── .env.example
└── instalar_dependencias.bat
```

Consulta `ARQUITECTURA.md` para el detalle técnico.

## PDF y dominios de evaluación

El informe separa deliberadamente:

1. **Salud técnica:** qué ocurrió realmente durante la sesión.
2. **Vigencia anual:** qué tan vigente es el hardware frente al contexto tecnológico del año actual.
3. **Plan de acción:** qué hacer únicamente cuando existe un problema técnico o advisory autorizado.

Un componente puede estar sano y ser poco vigente, o ser vigente y presentar un problema térmico. CorePulse no usa una de estas categorías como sustituto de la otra.

## Pruebas

Desde la raíz:

```powershell
python .\tests\test_integrity.py
python .\tests\test_startup.py
python .\tests\test_project_structure.py
python .\tests\test_hardware_policy.py
python .\tests\test_hardware_relevance.py
python .\tests\test_ai_diagnostics.py
python .\tests\test_ai_resilience.py
python .\tests\test_pdf.py
python .\tests\test_dashboard.py
python .\tests\test_branding.py
python .\tests\test_cpu_advanced_details.py
```

Diagnósticos live opcionales, que sí pueden consumir cuota de Groq:

```powershell
python .\tests\diagnose_ai_runtime.py
python .\tests\diagnose_hardware_relevance.py
```

## Seguridad y distribución

El paquete distribuible no incluye `.env`, claves API, `.git`, bases locales, historiales, logs, cachés, backups, payloads ni aplicadores de parches. `.env.example` es solo una plantilla segura.
