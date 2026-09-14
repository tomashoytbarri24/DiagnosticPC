# Versión actual: V126

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
- Versión actual: **V125**.

El sistema de runtime canónico NO depende del número de versión y se conserva desde la base universal corregida.

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
