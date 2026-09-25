# CorePulse — contrato de no regresión

Este archivo existe para integraciones futuras (humanas o asistidas por IA). Si una rama nueva se mezcla con CorePulse, estas reglas son **invariantes funcionales** y no deben eliminarse por "limpieza", refactor visual o reemplazo de módulos.

## Almacenamiento / salud real

- El porcentaje de salud de NVMe es evidencia real: `salud restante = 100 - Percentage Used`.
- Prioridad: NVMe Health Log nativo de Windows -> Storage Reliability/Wear -> Life/Health real de LHM -> `smartctl` como fallback lento.
- `SMART PASSED` / `Healthy` **nunca** se convierten en 100%.
- Si ya se obtuvo un porcentaje cuantitativo real (por ejemplo 94%), una lectura temporal fallida no puede reemplazarlo por `N/A`.
- Deben conservarse `save_storage_summary_health_cache()` y `load_storage_summary_health_cache()` y el refresco en dos fases de `main.py` (`include_slow_fallbacks=False/True`).
- El Dashboard consume `disk['health']`; `health_percent` queda sólo como compatibilidad antigua.

## Drivers

- No usar Windows Update Agent/COM.
- El inventario usa `Win32_PnPSignedDriver.HardWareID` sin ejecutar `Get-PnpDeviceProperty` por cada driver.
- La búsqueda online usa un máximo pequeño de hardware prioritario, consultas paralelas, timeout corto y caché local.
- Sólo se anuncia una actualización cuando se confirma versión superior compatible. No inferir actualización sólo por antigüedad.

## Temas

- Todos los temas son oscuros. No reintroducir temas claros.
- Mantener al menos 20 perfiles oscuros y contraste legible.

## Actualizaciones de CorePulse

- El módulo interno de Actualizaciones fue retirado en V319 por decisión de producto. No reintroducir `update_dialog`, `update_manager`, rollback ni publicación Git dentro de la UI sin una petición explícita.

## Verificación

Antes de entregar una integración, ejecutar `pytest -q`. `tests/test_v320_non_regression_contract.py` protege estas reglas clave.

## V321 — Arranque y temas en caliente

- El Dashboard no se revela hasta disponer de dos muestras reales aplicadas; durante el splash se precarga salud NVMe nativa rápida.
- Un porcentaje SMART/NVMe real cacheado o recién leído no debe degradarse a N/A por warm-up o fallo transitorio.
- La insignia de salud de cada disco debe permanecer pegada al extremo derecho de su tarjeta; "Ver detalles" se superpone sólo en hover y no reserva ancho.
- Aplicar un tema no debe reiniciar, cerrar ni relanzar CorePulse. El cambio debe realizarse dentro del mismo proceso mediante `apply_theme_live`.
- El borde exterior del sidebar debe cerrar después del último módulo visible y no extender una tarjeta vacía hasta el fondo de la ventana.

## V322 — regla de integración obligatoria

- Este archivo **no controla por sí solo a otra IA**. Es un contrato de aceptación: al integrar una versión de Tomás, el asistente debe leerlo y ejecutar los tests antes de entregar.
- No borrar ni modificar `COREPULSE_NON_REGRESSION_CONTRACT.md` ni los tests de no-regresión para hacer pasar una integración.
- Una lectura de arranque sin porcentaje no puede sobrescribir `health_label`, `health_source`, `wear` ni `health` de una lectura cuantitativa real previa.
- Si no existe caché cuantitativa válida, CorePulse puede mantener el splash brevemente mientras resuelve Storage Reliability/smartctl; el Dashboard no debe abrir con `Salud N/A` si el porcentaje real puede obtenerse durante ese gate.

## V323 — Driver Hub 2.0

- La vista principal de Drivers sólo muestra hardware importante, incidencias reales y actualizaciones compatibles confirmadas. El inventario completo queda en "Inventario avanzado".
- La búsqueda online usa Hardware ID, máximo pequeño de dispositivos prioritarios, `ThreadPoolExecutor`, timeout corto, caché de inventario y caché del último escaneo.
- `Instalar seleccionados` excluye firmware. Firmware sólo se instala individualmente.
- Antes de reemplazar un paquete OEM, CorePulse exporta el INF actual con `PnPUtil /export-driver`; si ese respaldo OEM falla, la instalación no continúa.
- Conservar enlaces a soporte oficial de fabricante como ayuda al usuario, sin afirmar que CorePulse consultó una API oficial cuando la compatibilidad se obtuvo desde Microsoft Update Catalog.

## Driver Hub — flujo protegido V326
- Una incidencia debe poder buscar actualización sin reconstruir toda la página.
- Si existe una versión superior compatible confirmada, la misma tarjeta debe exponer Descargar → Instalar.
- No convertir una incidencia local en “actualización disponible” sin confirmación por Hardware ID.

## V327 — Driver Hub multi-fuente

- Driver Hub no depende exclusivamente de Microsoft Update Catalog: puede usar resolvers oficiales de fabricante cuando la familia del hardware está validada y conserva Catalog como fallback por Hardware/Compatible ID.
- Intel Wireless Bluetooth debe comprobarse contra el canal oficial de Intel cuando el adaptador/familia es compatible; no ocultar esa fuente en refactors futuros.
- Sólo el pequeño lote prioritario puede consultar `Get-PnpDeviceProperty` para enriquecer Hardware/Compatible IDs; nunca recorrer ~170 drivers uno a uno.
- Descargas de fabricante deben validar SHA-256 cuando el fabricante lo publica y firma Authenticode antes de ejecutar.
- Los títulos del Resumen para recursos deben ser `Procesador`, `Memoria RAM` y `Tarjeta Gráfica`.
