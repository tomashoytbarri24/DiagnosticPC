# CorePulse V157 — Validación y entrega

Proyecto completo derivado de CorePulse_V156.zip, con cambios incrementales.
El documento de solicitud recibido termina a mitad de la última frase de la sección 9.

## Cambios

- Sesión identificada por token, evento de cancelación propio y estados explícitos.
- La UI consume un buzón acotado desde Tk; los workers no programan actualizaciones Tk.
- Cancelar limpia callbacks, resultado, snapshots y permisos de PDF; la vista se restablece al repetir.
- Repetir acepta la nueva ejecución de inmediato y espera a que termine la carga anterior antes de tomar muestras.
- Las consultas PowerShell/batería iniciadas dentro del diagnóstico pueden cancelarse; otras herramientas conservan su comportamiento.
- Cancelaciones, errores y respuestas tardías no se publican como diagnósticos completos; tampoco se guarda un benchmark interrumpido como terminado.
- CPU libera sus workers incluso si falla el observador. SSD cancelado calcula bytes realmente escritos. Archivos temporales y resultados usan nombres únicos.
- Una protección térmica durante estrés impide iniciar otra carga de benchmark.
- Evidencia: RAM y capacidad, frecuencias GPU, FPS y 1% low del workload OpenGL existente, almacenamiento y fuente de salud. No se confunde ese workload con FPS de un juego.
- Un renderer sin correspondencia verificable con sensores mantiene temperatura/uso N/A; se conservan eventos de throttling observados aunque luego desaparezcan.
- Se incorpora la caché de salud física existente con coincidencia de identidad, sin modificar el motor NVMe. Un estado Healthy sin porcentaje sigue siendo N/A.
- Windows vacío/parcial no se declara normal. La prioridad requiere un hallazgo real; salud física, estrés y rendimiento permanecen separados.
- Los motores de navegación, bandeja, temas, Gaming, reparación, historial, benchmark visual y PDF existentes se conservan.

## Pruebas realizadas

- Pruebas nuevas V157: **18 aprobadas, 1 omitida** por indisponibilidad de Tcl/Tk en el entorno.
- Incluyen cancelar/repetir en escritorio, Windows, CPU, RAM, GPU y benchmark; doble cancelación; callbacks antiguos; terminar después de cancelar; guardado y PDF bloqueados; protección térmica; cierre real de procesos propios; cancelación real CPU/RAM/SSD.
- Las cancelaciones por fase GPU y la orquestación usan motores sustituidos controlados. No equivalen a certificación física de una GPU.
- Suite pytest heredada: V156 tuvo **85 aprobadas y 44 fallidas**. V157 tuvo **102 aprobadas, 45 fallidas y 1 omitida**, incluyendo las pruebas nuevas.
- La única falla adicional de la suite heredada exige literalmente VERSION="156" y se explica por la versión 157. No se alteraron ni ocultaron los tests históricos para hacerlos pasar.
- 28 scripts heredados adicionales: **10 aprobados y 18 fallidos en ambas versiones**, con los mismos estados. Entre los aprobados: estructura, integridad, sintaxis de arranque, parser NVMe, almacenamiento, seguridad de comandos, drivers, política de hardware y generación real de PDF.
- Todos los módulos Python entregados se analizaron con ast.parse. Se verificó la integridad CRC del ZIP y su contenido completo.

## Límites de validación

No se certifica una ejecución gráfica completa ni compatibilidad física en todos los equipos. Tcl/Tk no pudo leer init.tcl en este entorno; la prueba con widgets reales se omitió explícitamente. Los tests de arranque aprobados verifican código/estructura, no una sesión interactiva de la aplicación.
La cancelación es cooperativa: una llamada nativa al controlador GPU o E/S bloqueada por Windows puede tardar en devolver el control. La siguiente sesión espera su liberación para no mezclar cargas.
La mayoría de fallos heredados fijan versiones/textos de versiones anteriores; otros corresponden a contratos históricos de publicación/actualización y al entorno. Se conserva su inventario en PRUEBAS_V157.json.

## Ejecución

Extraer la carpeta completa y abrir **Iniciar_CorePulse.bat** o **CorePulse.vbs**, como en V156.
Se conserva el bootstrap y el archivo de dependencias bloqueadas originales. Es una distribución fuente; requiere el runtime/dependencias de CorePulse y no incluye un EXE nuevo.

Pruebas nuevas reproducibles: `python -m unittest tests.test_v157_diagnostic_lifecycle -v` desde la carpeta del proyecto con sus dependencias instaladas.

## Archivos protegidos

SHA-256 idéntico antes y después en los cinco archivos solicitados:

- `core/runtime_venv_path.py`: `263d725dc8a50ef57d2e0dd8d8827968f58d2b67dcee6b0a276ca6dd8d562e92`
- `bootstrap_corepulse.py`: `925d4ef090b28c27ceffbbbba9362a8137f665212ac445e96a096c0ce5e17a0b`
- `core/source_runtime_bootstrap.py`: `bde37780c35ebc280b0b22ac6a71926051ae9fde48b65935b6af64b819f7ccfd`
- `requirements-runtime-lock.txt`: `36ee044c5dab3c5c8cfecbe0456923c9f406d83a93ef04d93f9fd27f1566c706`
- `core/nvme_smart_windows.py`: `fe9481d270d5b47299b97fc97d37ee56f65bd904333f634255e4a91e63958283`

No se ejecutaron reparaciones de Windows, ni se publicó el proyecto en un repositorio remoto.
