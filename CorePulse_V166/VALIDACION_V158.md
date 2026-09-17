# CorePulse V158 — Validación y entrega

Proyecto completo derivado de CorePulse_V157.zip, con una mejora incremental enfocada: fluidez de la ventana al redimensionar (punto 6 de la solicitud). El resto de los puntos se revisó explícitamente y no requirió cambios (ver "Puntos revisados sin cambios" abajo).

## Cambio principal: redibujo CTk coalescido durante resize

**Causa raíz identificada.** El debounce de `gui/dashboard_layout.py` instalado desde V148 (detector trailing único sobre `<Configure>` de la ventana raíz) protege el trabajo propio de CorePulse — reflow de gráficos, cambio de modo de layout, alturas de tarjetas — pero nunca pudo tocar el verdadero costo del arrastre del borde: **CustomTkinter enlaza `<Configure>` directamente en cada widget** (`CTkBaseClass._update_dimensions_event`) y llama a `self._draw()` de forma síncrona en cuanto ese widget cambia de tamaño en píxeles. Cuando Windows redimensiona en tiempo real todos los widgets `sticky='nsew'`/`fill='both'` de la jerarquía durante el arrastre, cada uno dispara su propio redibujo de Canvas de forma independiente — cientos de redibujos por segundo con las tarjetas, medidores y botones visibles en el Dashboard/Diagnóstico, completamente al margen del debounce de la aplicación.

**Solución.** Nuevo módulo `gui/resize_render_guard.py`: mientras `app.is_resizing` está activo, los redibujos de `CTkBaseClass` se coalescen en un `WeakSet` en vez de ejecutarse de inmediato, y se aplican una sola vez por widget al soltar el borde (`set_active(False)` → `flush()`). Fuera de un resize activo el comportamiento es idéntico al original de CustomTkinter.

**Integración.**
- `main.py`: `install()` se llama justo después de `import customtkinter as ctk` y antes de cualquier otro import de `gui.*`, para que el parche esté activo antes de crear el primer widget.
- `gui/dashboard_layout.py`: se añadió `_set_resizing(app, active)` como único punto que asigna `app.is_resizing` y sincroniza la guarda (`set_active`). Las 5 asignaciones directas anteriores (`_finish`, `_enter`, `_exit`, y los dos puntos del detector trailing en `_install_layout_authority`) ahora pasan por esa función.
- El detector trailing de V148 (`RESIZE_DEBOUNCE_MS`, único callback `after` reprogramado) **no se tocó**: la guarda de V158 es un complemento a nivel de widget, no un reemplazo.

**Qué no cambia.** Ningún archivo de telemetría, diagnóstico, benchmark o REAL_OR_NA. Si en una versión futura de CustomTkinter cambia la firma interna de `_update_dimensions_event`, `install()` falla en silencio y CorePulse simplemente vuelve al comportamiento sin coalescer — no rompe el arranque.

## Puntos revisados sin cambios

Se revisó explícitamente cada punto de la solicitud contra el código de V157 antes de decidir no tocarlo:

- **Diagnóstico Completo (punto 4):** ciclo de vida, cancelación, evidencia por componente y separación estado físico / estrés / rendimiento ya estaban completos desde V142–V157. No se modificó `core/diagnostic_lifecycle.py`, `core/diagnostic_session.py`, `core/complete_diagnostic.py` ni `core/cancellable_process.py`.
- **Drivers (punto 8):** el texto `"Antiguo · revisar actualización"` y la aclaración explícita de que "antiguo" no implica una actualización confirmada ya están en `gui/health_center_panel.py`. No existe descarga/instalación automática de drivers.
- **Benchmark (punto 9):** `core/visual_benchmark.py` ya filtra `phase_specs` por `selected_components`; una ejecución sólo-GPU no incluye la fase `CPU / Multinúcleo`, por lo que no hay mezcla de resultados.
- **Bandeja (punto 10):** la X de Windows llama a `minimize_to_tray` (oculta, no cierra) y `"Salir de CorePulse"` en el ícono de bandeja llama a `on_close` (cierre real). Ya correcto.
- **Publicar en Git (punto 7):** `gui/update_dialog.py` ya muestra repositorio local, remote, rama, URL remota, versión/carpeta a publicar y estado de FASE 1/2/3; `core/developer_publisher.py` ya bloquea `main`/`master`/`trunk`. No se tocó.

## Archivos modificados

- `gui/resize_render_guard.py` — **nuevo**. Guarda de redibujo CTk.
- `tests/test_v158_resize_render_guard.py` — **nuevo**. 8 pruebas (4 de contrato sobre el código fuente + 4 con widgets Tk reales).
- `main.py` — 3 líneas: import + llamada a `install()` antes de los imports de `gui.*`.
- `gui/dashboard_layout.py` — se añadió `_set_resizing()` y se reemplazaron las 5 asignaciones directas a `app.is_resizing` por llamadas a esa función.
- `core/version.py`, `LATEST_VERSION.txt`, `VERSIONING.md`, `README.md` — versión y changelog.

Ningún otro archivo del proyecto fue modificado.

## Pruebas realizadas

Este entorno sí tuvo Tcl/Tk disponible (instalado junto con Xvfb para un display virtual), a diferencia del entorno de V157, que no pudo ejecutar widgets reales.

- **Pruebas nuevas V158** (`tests.test_v158_resize_render_guard`): **8 aprobadas, 0 falladas**, incluidas 3 con widgets `CTk` reales bajo Xvfb: coalescencia durante resize activo y aplicación única al soltar; un widget destruido mientras está pendiente no lanza excepción al hacer flush; el ciclo de vida de `DiagnosticRun` (iniciar → cancelar → reiniciar con token distinto) no se ve afectado por que la guarda esté activa.
- **Regresión dirigida** (`tests.test_v157_diagnostic_lifecycle` + `tests.test_v148_fluid_resize_diagnostic`, 19 pruebas): **19/19 aprobadas**, incluida la prueba con panel Tk real de cancelar/repetir/completar tres veces seguidas.
- **Suite completa vía pytest** (excluyendo 15 archivos que son scripts standalone, no módulos pytest — ver abajo): **113 aprobadas, 45 falladas** (más 11 subtests). Se comparó la lista exacta de las 45 fallas contra una corrida idéntica sobre el V157 original sin modificar: **son las mismas 45, una por una** — todas pruebas históricas `test_vXXX_*` que fijan literalmente `VERSION == "XXX"` de una versión anterior (142 a 156) y, en algunos casos, una aserción de comportamiento ya superada por una versión posterior. Ninguna falla nueva.
- **15 scripts heredados** que no son módulos pytest (usan `raise SystemExit(...)` a nivel de módulo): se ejecutaron directamente como `python3 <script>` y se comparó el código de salida contra el V157 original. **Resultado idéntico en los 15** (11 con éxito, 4 con fallas preexistentes no relacionadas con este cambio: `test_battery_summary_visual_parity.py`, `test_battery_wear_state_visual.py`, `test_branding.py`, `test_pdf_button_flow.py`).
- **Sintaxis:** `python3 -m compileall .` y `ast.parse` sobre los 372 archivos `.py` del proyecto — 0 errores.
- **Archivos protegidos:** SHA-256 idéntico antes y después en los cinco archivos solicitados (ver abajo).

## Límites de validación

No se certifica una sesión interactiva completa en Windows real (fuera del entorno de build no se pudo probar el arrastre físico del borde de la ventana con mouse, DPI real ni GPU real). La guarda de redibujo se validó con Tk real bajo Xvfb (Linux, sin GPU), simulando el cambio de geometría vía `root.geometry(...)` y verificando que el redibujo se coalesce y se aplica exactamente una vez — no se midió framerate real en Windows. Recomendado: confirmar en un PC Windows real que el arrastre del borde se siente más fluido, especialmente en pantallas con muchas tarjetas visibles (Diagnóstico Completo, Centro de Salud).

Los 45 fallos heredados y los 4 fallos de scripts standalone son idénticos a V157 y no se investigaron ni "arreglaron" en esta entrega — corresponden a contratos de versiones anteriores, tal como ya documentaba VALIDACION_V157.md para el caso de V156.

## Archivos protegidos

SHA-256 idéntico antes y después en los cinco archivos solicitados:

- `core/runtime_venv_path.py`: `263d725dc8a50ef57d2e0dd8d8827968f58d2b67dcee6b0a276ca6dd8d562e92`
- `bootstrap_corepulse.py`: `925d4ef090b28c27ceffbbbba9362a8137f665212ac445e96a096c0ce5e17a0b`
- `core/source_runtime_bootstrap.py`: `bde37780c35ebc280b0b22ac6a71926051ae9fde48b65935b6af64b819f7ccfd`
- `requirements-runtime-lock.txt`: `36ee044c5dab3c5c8cfecbe0456923c9f406d83a93ef04d93f9fd27f1566c706`
- `core/nvme_smart_windows.py`: `fe9481d270d5b47299b97fc97d37ee56f65bd904333f634255e4a91e63958283`

No se ejecutaron reparaciones de Windows ni se publicó el proyecto en un repositorio remoto.

## Ejecución

Extraer la carpeta completa y abrir **Iniciar_CorePulse.bat** o **CorePulse.vbs**, como en V157. Se conserva el bootstrap y el archivo de dependencias bloqueadas originales.

Pruebas nuevas reproducibles: `python -m unittest tests.test_v158_resize_render_guard -v` desde la carpeta del proyecto con sus dependencias instaladas (requiere Tcl/Tk; las 4 pruebas de contrato sobre el código fuente no lo necesitan).
