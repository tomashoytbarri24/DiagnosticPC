# VALIDACIÓN V280 — SIDEBAR INSTANT TOGGLE FIX

## Base
- V279

## Problema observado
En el video de validación de V279, cerrar y reabrir el sidebar mostraba frames parciales: restos de botones, tarjetas cortadas y contenido del dashboard redibujado por fragmentos. La reapertura además se sentía lenta.

## Causa corregida
`set_sidebar_collapsed()` reconstruía todo el sidebar con `_rebuild_sidebar()` cada vez que se reabría y luego ejecutaba `request_stable_layout_sync(force=True)`, forzando un relayout completo de tarjetas, charts y widgets.

## Cambios
- El sidebar se crea una vez y se conserva vivo al ocultarse.
- Reapertura mediante `grid()` del mismo árbol ya construido.
- Se elimina `_rebuild_sidebar()` del toggle.
- Se elimina la resincronización global forzada del dashboard en el toggle.
- Se cancelan restos de antiguos efectos de movimiento antes del cambio de geometría.
- El control de reapertura se reposiciona con `after_idle`, sin bloquear el hilo de Tk.

## Debe comprobarse en Windows
1. Cerrar/abrir el sidebar repetidamente y de forma rápida.
2. Confirmar que no aparecen widgets parciales o residuos visuales.
3. Confirmar que el dashboard no se siente pausado durante el toggle.
4. Confirmar que la X hover y el botón ☰ siguen funcionando.
